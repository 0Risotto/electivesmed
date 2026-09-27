"""Contacts: list, import, score, scout, detail, compliance, data rights."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from ....compliance import DEFAULT_LAWFUL_BASIS, LAWFUL_BASIS_VALUES
from ....converters.contact import contact_to_view
from ....converters.draft import draft_to_preview
from ....converters.summary import summary_to_view
from ....models.enums import AgentName
from ....models.views import InvocationView
from ....services.importing import import_contacts_csv
from ....services.scoring import score_contacts as score_contacts_activity
from ....utils.ids import new_invocation_id
from ..deps import get_container, get_runner
from ..helpers import redirect_with_flash
from ..jobs import run_scout
from ..templating import templates

router = APIRouter(prefix="/contacts")


def _load(container, contact_id: int):
    contact = container.dao.get_contact(contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact


@router.get("", response_class=HTMLResponse)
def list_contacts(
    request: Request,
    q: str = "",
    status: str = "",
    country: str = "",
    container=Depends(get_container),
):
    contacts = container.dao.find_contacts(with_email_only=False, limit=200)
    if q:
        needle = q.lower()
        contacts = [
            c
            for c in contacts
            if needle
            in " ".join(
                filter(None, [c.name, c.title, c.hospital_name, c.email_value])
            ).lower()
        ]
    if status:
        contacts = [c for c in contacts if str(c.status) == status]
    if country:
        contacts = [
            c for c in contacts if (c.country or "").upper() == country.upper()
        ]
    contact_views = [contact_to_view(c) for c in contacts]
    summary = summary_to_view(
        container.dao.summary(), container.settings.limits.daily_send_cap
    )
    return templates.TemplateResponse(
        request,
        "contacts/list.html",
        {
            "contacts": contact_views,
            "summary": summary,
            "q": q,
            "status": status,
            "country": country,
        },
    )


@router.post("/import")
def import_upload(
    request: Request,
    upload: UploadFile = File(...),
    hospital: str = Form(""),
    country: str = Form(""),
    container=Depends(get_container),
):
    text = upload.file.read().decode("utf-8-sig", errors="replace")
    result = import_contacts_csv(
        container,
        text,
        hospital_name=hospital,
        country=country,
        source_url=upload.filename or "",
    )
    return redirect_with_flash(
        "/contacts", f"imported {result['saved']} contacts ({result['rows_seen']} rows)"
    )


@router.post("/score")
def score_contacts(request: Request, limit: int = Form(50), container=Depends(get_container)):
    result = score_contacts_activity(container, limit=limit)
    return redirect_with_flash(
        "/contacts", f"scored {result['scored']} contacts ({result.get('method', 'n/a')})"
    )


@router.post("/scout")
def scout(
    request: Request,
    instructions: str = Form(""),
    campaign: str = Form(""),
    container=Depends(get_container),
    runner=Depends(get_runner),
):
    invocation_id = new_invocation_id()
    campaign_id = None
    if campaign:
        existing = container.dao.get_campaign(campaign)
        campaign_id = existing.id if existing else None
    runner.submit(run_scout, container, invocation_id, instructions, campaign_id)
    view = InvocationView(
        id=invocation_id,
        agent=AgentName.SCOUT.value,
        status="running",
        campaign_id=campaign_id,
        started_at="",
        finished_at=None,
        error=None,
        output=None,
    )
    return templates.TemplateResponse(
        request, "partials/invocation_status.html", {"invocation": view}
    )


@router.get("/{contact_id}", response_class=HTMLResponse)
def contact_detail(request: Request, contact_id: int, container=Depends(get_container)):
    contact = _load(container, contact_id)
    drafts = [
        draft_to_preview(draft, contact)
        for draft in container.dao.find_drafts(limit=100)
        if draft.contact_id == contact_id
    ]
    export = (
        container.dao.export_contact(contact.email_value)
        if contact.email_value
        else {"sends": []}
    )
    return templates.TemplateResponse(
        request,
        "contacts/detail.html",
        {
            "contact": contact,
            "drafts": drafts,
            "sends": export["sends"],
            "lawful_bases": LAWFUL_BASIS_VALUES,
        },
    )


@router.post("/{contact_id}/compliance")
def update_compliance(
    request: Request,
    contact_id: int,
    country: str = Form(""),
    timezone: str = Form(""),
    lawful_basis: str = Form(DEFAULT_LAWFUL_BASIS),
    container=Depends(get_container),
):
    _load(container, contact_id)
    basis = lawful_basis if lawful_basis in LAWFUL_BASIS_VALUES else DEFAULT_LAWFUL_BASIS
    container.dao.update_contact_compliance(
        contact_id, country.strip().upper() or None, timezone.strip() or None, basis
    )
    return redirect_with_flash(f"/contacts/{contact_id}", "compliance fields updated")


@router.get("/{contact_id}/export")
def export_contact(contact_id: int, container=Depends(get_container)):
    contact = _load(container, contact_id)
    payload = container.dao.export_contact(contact.email_value or "")
    return JSONResponse(payload)


@router.post("/{contact_id}/erase")
def erase_contact(
    request: Request,
    contact_id: int,
    confirm: str = Form(""),
    container=Depends(get_container),
):
    contact = _load(container, contact_id)
    expected = contact.email_value or ""
    if confirm.strip().lower() != expected:
        return redirect_with_flash(f"/contacts/{contact_id}", "erase cancelled: email did not match")
    result = container.dao.erase_contact(expected)
    return redirect_with_flash(
        "/contacts", f"erased {result['contacts_deleted']} contact records for {expected}"
    )
