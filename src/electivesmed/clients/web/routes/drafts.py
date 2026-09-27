"""Drafts: inbox, personalization editor, lint, approve/reject/suppress, regenerate."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ....actions.suppression import suppress as suppress_action
from ....builders.payloads import build_payload
from ....components.email_style import EmailStyleChecker
from ....constants import regions
from ....converters.draft import draft_to_preview
from ....errors import AttachmentError
from ....models.enums import AgentName, DraftStatus
from ....models.views import InvocationView
from ....services.attachments import attach_to_draft, draft_attachments, remove_from_draft
from ....utils.ids import new_invocation_id
from ....utils.text import word_count
from ..deps import get_container, get_runner
from ..helpers import redirect_with_flash
from ..jobs import run_regenerate
from ..templating import templates

router = APIRouter(prefix="/drafts")

_STATUS_FILTERS = {
    "pending": DraftStatus.PENDING,
    "approved": DraftStatus.APPROVED,
    "rejected": DraftStatus.REJECTED,
    "sent": DraftStatus.SENT,
    "send_failed": DraftStatus.SEND_FAILED,
}


def _load(container, draft_id: int):
    draft = container.dao.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return draft


def _lint(subject: str, body: str) -> dict:
    checker = EmailStyleChecker()
    return {
        "violations": checker.violations(f"{subject}\n{body}"),
        "words": word_count(body),
    }


@router.get("", response_class=HTMLResponse)
def inbox(
    request: Request,
    status: str = "pending",
    limit: int = 100,
    container=Depends(get_container),
):
    status_filter = _STATUS_FILTERS.get(status, DraftStatus.PENDING)
    drafts = container.dao.find_drafts(status_filter, limit=limit)
    previews = [
        draft_to_preview(draft, container.dao.get_contact(draft.contact_id))
        for draft in drafts
    ]
    return templates.TemplateResponse(
        request,
        "drafts/inbox.html",
        {"drafts": previews, "status": status},
    )


@router.get("/{draft_id}", response_class=HTMLResponse)
def editor(request: Request, draft_id: int, container=Depends(get_container)):
    draft = _load(container, draft_id)
    contact = container.dao.get_contact(draft.contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    preview = draft_to_preview(draft, contact)
    lint = _lint(draft.subject, draft.body_text)

    payload_preview = ""
    if contact.email is not None:
        settings = container.settings
        payload = build_payload(
            draft,
            contact,
            from_email=settings.sender.email or settings.smtp.from_email,
            reply_to=settings.sender.reply_to or None,
            include_opt_out=settings.sending.include_opt_out,
            postal_address=settings.sender.postal_address,
            sender_name=settings.sender.name,
            organization=settings.sender.organization,
        )
        payload_preview = payload.body_text

    campaign = (
        container.dao.get_campaign_by_id(draft.campaign_id)
        if draft.campaign_id
        else None
    )
    jurisdiction = regions.profile_for(
        contact.country, container.settings.compliance.jurisdiction_overrides
    )
    return templates.TemplateResponse(
        request,
        "drafts/editor.html",
        {
            "draft": draft,
            "preview": preview,
            "contact": contact,
            "lint": lint,
            "payload_preview": payload_preview,
            "campaign": campaign,
            "jurisdiction": jurisdiction,
            "attachments": draft_attachments(container, draft.id or 0),
            "library": container.dao.list_attachments(limit=500),
        },
    )


@router.post("/{draft_id}/attach")
def attach(
    request: Request,
    draft_id: int,
    attachment_ids: list[int] = Form(default=[]),
    container=Depends(get_container),
):
    _load(container, draft_id)
    if not attachment_ids:
        return redirect_with_flash(f"/drafts/{draft_id}", "no documents selected")
    errors: list[str] = []
    for attachment_id in attachment_ids:
        try:
            attach_to_draft(container, draft_id, attachment_id)
        except AttachmentError as exc:
            errors.append(str(exc))
    if errors:
        return redirect_with_flash(f"/drafts/{draft_id}", f"attach failed: {errors[0]}")
    return redirect_with_flash(
        f"/drafts/{draft_id}", f"attached {len(attachment_ids)} document(s)"
    )


@router.post("/{draft_id}/detach")
def detach(
    request: Request,
    draft_id: int,
    attachment_id: int = Form(...),
    container=Depends(get_container),
):
    _load(container, draft_id)
    remove_from_draft(container, draft_id, attachment_id)
    return redirect_with_flash(f"/drafts/{draft_id}", "attachment removed")


@router.post("/{draft_id}/save")
def save(
    request: Request,
    draft_id: int,
    subject: str = Form(""),
    body: str = Form(""),
    container=Depends(get_container),
):
    _load(container, draft_id)
    if not subject.strip() or not body.strip():
        return redirect_with_flash(f"/drafts/{draft_id}", "subject and body are required")
    container.dao.update_draft_body(draft_id, subject.strip(), body.strip(), None)
    return redirect_with_flash(f"/drafts/{draft_id}", "draft saved")


@router.post("/{draft_id}/lint", response_class=HTMLResponse)
def lint(
    request: Request,
    draft_id: int,
    subject: str = Form(""),
    body: str = Form(""),
    container=Depends(get_container),
):
    _load(container, draft_id)
    return templates.TemplateResponse(
        request, "partials/lint.html", _lint(subject, body)
    )


@router.post("/{draft_id}/approve")
def approve(request: Request, draft_id: int, container=Depends(get_container)):
    _load(container, draft_id)
    container.dao.set_draft_status(draft_id, DraftStatus.APPROVED)
    return redirect_with_flash("/drafts", f"approved draft #{draft_id}")


@router.post("/{draft_id}/reject")
def reject(request: Request, draft_id: int, container=Depends(get_container)):
    _load(container, draft_id)
    container.dao.set_draft_status(draft_id, DraftStatus.REJECTED)
    return redirect_with_flash("/drafts", f"rejected draft #{draft_id}")


@router.post("/{draft_id}/suppress")
def suppress(request: Request, draft_id: int, container=Depends(get_container)):
    draft = _load(container, draft_id)
    contact = container.dao.get_contact(draft.contact_id)
    if contact is not None and contact.email_value:
        suppress_action(container, contact.email_value, "review")
    container.dao.set_draft_status(draft_id, DraftStatus.REJECTED)
    return redirect_with_flash("/drafts", f"suppressed and rejected draft #{draft_id}")


@router.post("/{draft_id}/regenerate", response_class=HTMLResponse)
def regenerate(
    request: Request,
    draft_id: int,
    instructions: str = Form(""),
    container=Depends(get_container),
    runner=Depends(get_runner),
):
    draft = _load(container, draft_id)
    contact = container.dao.get_contact(draft.contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    campaign = (
        container.dao.get_campaign_by_id(draft.campaign_id) if draft.campaign_id else None
    )
    invocation_id = new_invocation_id()
    runner.submit(run_regenerate, container, invocation_id, contact, campaign, instructions)
    view = InvocationView(
        id=invocation_id,
        agent=AgentName.OUTREACH.value,
        status="running",
        campaign_id=campaign.id if campaign else None,
        started_at="",
        finished_at=None,
        error=None,
        output=None,
    )
    return templates.TemplateResponse(
        request, "partials/invocation_status.html", {"invocation": view}
    )


@router.post("/bulk")
def bulk(
    request: Request,
    action: str = Form(...),
    draft_ids: list[int] = Form(default=[]),
    container=Depends(get_container),
):
    past_tense = {"approve": "approved", "reject": "rejected", "suppress": "suppressed"}
    if action not in past_tense:
        return redirect_with_flash("/drafts", f"unknown action {action!r}")
    for draft_id in draft_ids:
        draft = container.dao.get_draft(draft_id)
        if draft is None:
            continue
        if action == "suppress":
            contact = container.dao.get_contact(draft.contact_id)
            if contact is not None and contact.email_value:
                suppress_action(container, contact.email_value, "review")
            container.dao.set_draft_status(draft_id, DraftStatus.REJECTED)
        elif action == "approve":
            container.dao.set_draft_status(draft_id, DraftStatus.APPROVED)
        else:
            container.dao.set_draft_status(draft_id, DraftStatus.REJECTED)
    return redirect_with_flash("/drafts", f"{past_tense[action]} {len(draft_ids)} drafts")
