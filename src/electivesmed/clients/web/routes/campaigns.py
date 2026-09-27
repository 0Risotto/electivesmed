"""Campaigns: list, create, generate drafts for top contacts."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ....models.entities import Campaign
from ....models.enums import AgentName
from ....models.views import InvocationView
from ....utils.ids import new_invocation_id
from ..deps import get_container, get_runner
from ..helpers import redirect_with_flash
from ..jobs import run_generate
from ..templating import templates

router = APIRouter(prefix="/campaigns")


def _select_contacts(container, limit: int, min_score: float) -> list:
    contacts = [
        c
        for c in container.dao.find_contacts(scored_only=True, limit=limit * 3)
        if (c.fit_score or 0.0) >= min_score
    ][:limit]
    if not contacts:
        contacts = container.dao.find_contacts(with_email_only=True, limit=limit)
    return contacts


@router.get("", response_class=HTMLResponse)
def list_campaigns(request: Request, container=Depends(get_container)):
    campaigns = container.dao.find_campaigns(limit=50)
    return templates.TemplateResponse(
        request, "campaigns/list.html", {"campaigns": campaigns}
    )


@router.post("")
def create_campaign(
    request: Request,
    name: str = Form(...),
    goal: str = Form(""),
    tone: str = Form(""),
    language: str = Form("en"),
    container=Depends(get_container),
):
    if not name.strip():
        return redirect_with_flash("/campaigns", "campaign name is required")
    container.dao.upsert_campaign(
        Campaign(
            name=name.strip(),
            goal=goal.strip() or container.profile.goal,
            tone=tone.strip() or container.profile.tone,
            language=language.strip() or "en",
        )
    )
    return redirect_with_flash("/campaigns", f"campaign {name!r} saved")


@router.post("/{campaign_id}/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    campaign_id: int,
    limit: int = Form(5),
    min_score: float = Form(0.3),
    instructions: str = Form(""),
    container=Depends(get_container),
    runner=Depends(get_runner),
):
    campaign = container.dao.get_campaign_by_id(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    contacts = _select_contacts(container, limit, min_score)
    if not contacts:
        return redirect_with_flash(
            "/campaigns", "no contacts available; run ingest/import and score first"
        )
    invocation_id = new_invocation_id()
    runner.submit(run_generate, container, invocation_id, campaign, contacts, instructions)
    view = InvocationView(
        id=invocation_id,
        agent=AgentName.OUTREACH.value,
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
