"""Dashboard: pipeline summary, pending drafts, recent invocations."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ....converters.draft import draft_to_preview
from ....converters.invocation import invocation_to_view
from ....converters.summary import summary_to_view
from ....models.enums import DraftStatus
from ....models.views import InvocationView
from ..deps import get_container
from ..templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, container=Depends(get_container)):
    summary = summary_to_view(
        container.dao.summary(), container.settings.limits.daily_send_cap
    )
    invocations = [invocation_to_view(i) for i in container.dao.find_invocations(8)]
    pending = [
        draft_to_preview(draft, container.dao.get_contact(draft.contact_id))
        for draft in container.dao.find_drafts(DraftStatus.PENDING, limit=5)
    ]
    campaigns = container.dao.find_campaigns(limit=5)
    checks = [
        {"label": "Add DeepSeek key", "hint": "DEEPSEEK_API_KEY in .env", "done": container.llm.available, "href": "/sources"},
        {"label": "Configure SMTP", "hint": "SMTP_HOST/USER/PASSWORD in .env", "done": bool(container.mail.host), "href": "/sources"},
        {"label": "Ingest a source", "hint": "CMS, OSM, Wikidata, or your CSV", "done": summary.hospitals > 0, "href": "/sources"},
        {"label": "Add contacts", "hint": "import a CSV or run the scout", "done": summary.contacts > 0, "href": "/contacts"},
        {"label": "Score contacts", "hint": "rank by fit against profile.yaml", "done": summary.contacts_scored > 0, "href": "/contacts"},
        {"label": "Create a campaign", "hint": "goal and tone for the outreach", "done": bool(campaigns), "href": "/campaigns"},
        {
            "label": "Generate drafts",
            "hint": "DeepSeek writes one email per contact",
            "done": (summary.drafts_pending + summary.drafts_approved) > 0,
            "href": "/campaigns",
        },
        {"label": "Review and send", "hint": "approve, dry-run, then send", "done": summary.sent_total > 0, "href": "/send"},
    ]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "invocations": invocations,
            "pending": pending,
            "campaigns": campaigns,
            "checks": checks,
            "checks_done": sum(1 for check in checks if check["done"]),
        },
    )


@router.get("/invocations/{invocation_id}/status", response_class=HTMLResponse)
def invocation_status(
    invocation_id: str, request: Request, container=Depends(get_container)
):
    invocation = container.dao.get_invocation(invocation_id)
    if invocation is None:
        view = InvocationView(
            id=invocation_id,
            agent="job",
            status="running",
            campaign_id=None,
            started_at="",
            finished_at=None,
            error=None,
            output=None,
        )
    else:
        view = invocation_to_view(invocation)
    return templates.TemplateResponse(
        request, "partials/invocation_status.html", {"invocation": view}
    )
