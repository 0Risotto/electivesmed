"""Send: dry-run preview and guarded real sends."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from ....agent.invoker import manual_invocation
from ....builders.payloads import build_payload
from ....converters.draft import draft_to_preview
from ....models.enums import DraftStatus
from ....models.views import InvocationView
from ....services.attachments import mail_attachments
from ....services.sending import send_batch
from ....utils.ids import new_invocation_id
from ..deps import get_container, get_runner
from ..helpers import redirect_with_flash
from ..jobs import run_send
from ..templating import templates

router = APIRouter(prefix="/send")


def _approved(container, draft_ids: list[int] | None, limit: int = 20) -> list[int]:
    if draft_ids:
        return [draft_id for draft_id in draft_ids if container.dao.get_draft(draft_id)]
    return [
        draft.id
        for draft in container.dao.find_drafts(DraftStatus.APPROVED, limit=limit)
        if draft.id is not None
    ]


@router.get("", response_class=HTMLResponse)
def send_page(request: Request, container=Depends(get_container)):
    approved = container.dao.find_drafts(DraftStatus.APPROVED, limit=50)
    previews = [
        draft_to_preview(draft, container.dao.get_contact(draft.contact_id))
        for draft in approved
    ]
    return templates.TemplateResponse(
        request, "send.html", {"drafts": previews}
    )


@router.post("/dry-run", response_class=HTMLResponse)
def dry_run(
    request: Request,
    draft_ids: list[int] = Form(default=[]),
    force_window: bool = Form(False),
    container=Depends(get_container),
):
    ids = _approved(container, draft_ids)
    if not ids:
        return redirect_with_flash("/send", "no approved drafts to preview")
    previews = []
    for draft_id in ids:
        draft = container.dao.get_draft(draft_id)
        contact = container.dao.get_contact(draft.contact_id)
        if contact is None or contact.email is None:
            continue
        payload = build_payload(
            draft,
            contact,
            from_email=container.settings.sender.email or container.settings.smtp.from_email,
            reply_to=container.settings.sender.reply_to or None,
            include_opt_out=container.settings.sending.include_opt_out,
            postal_address=container.settings.sender.postal_address,
            sender_name=container.settings.sender.name,
            organization=container.settings.sender.organization,
        )
        previews.append(
            {
                "to": payload.to,
                "subject": payload.subject,
                "body": payload.body_text,
                "attachments": [item.filename for item in mail_attachments(container, draft_id)],
            }
        )
    with manual_invocation(container, "web-dry-run") as run:
        result = send_batch(container, ids, limit=len(ids), dry_run=True, force_window=force_window)
        run.output.update(result)
    return templates.TemplateResponse(
        request, "send_results.html", {"result": result, "previews": previews}
    )


@router.post("/real", response_class=HTMLResponse)
def real_send(
    request: Request,
    confirm: str = Form(""),
    draft_ids: list[int] = Form(default=[]),
    force_window: bool = Form(False),
    container=Depends(get_container),
    runner=Depends(get_runner),
):
    ids = _approved(container, draft_ids)
    if not ids:
        return redirect_with_flash("/send", "no approved drafts to send")
    expected = f"SEND {len(ids)}"
    if confirm.strip() != expected:
        return redirect_with_flash("/send", f"confirmation did not match ({expected})")
    invocation_id = new_invocation_id()
    runner.submit(run_send, container, invocation_id, ids, force_window)
    view = InvocationView(
        id=invocation_id,
        agent="web-send",
        status="running",
        campaign_id=None,
        started_at="",
        finished_at=None,
        error=None,
        output=None,
    )
    return templates.TemplateResponse(
        request, "partials/invocation_status.html", {"invocation": view}
    )
