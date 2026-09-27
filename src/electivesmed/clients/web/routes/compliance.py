"""Compliance: suppression list, retention purge, data-rights info."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from ....actions.suppression import suppress as suppress_action
from ....converters.summary import summary_to_view
from ..deps import get_container
from ..helpers import redirect_with_flash
from ..templating import templates

router = APIRouter(prefix="/compliance")


@router.get("", response_class=HTMLResponse)
def compliance_page(request: Request, container=Depends(get_container)):
    suppressions = container.dao.list_suppressions(limit=500)
    summary = summary_to_view(
        container.dao.summary(), container.settings.limits.daily_send_cap
    )
    return templates.TemplateResponse(
        request,
        "compliance.html",
        {
            "suppressions": suppressions,
            "summary": summary,
            "retention_days": container.settings.compliance.retention_days,
            "eu_policy": container.settings.compliance.eu_policy,
            "us_policy": container.settings.compliance.us_policy,
        },
    )


@router.post("/suppress")
def suppress(
    request: Request,
    email: str = Form(...),
    reason: str = Form("manual"),
    container=Depends(get_container),
):
    result = suppress_action(container, email, reason)
    if result.get("status") == "error":
        return redirect_with_flash("/compliance", result["error"])
    return redirect_with_flash("/compliance", f"suppressed {result['email']}")


@router.post("/purge")
def purge(request: Request, days: int = Form(...), container=Depends(get_container)):
    result = container.dao.purge_older_than(days)
    return redirect_with_flash(
        "/compliance",
        f"purged {result['contacts_deleted']} contacts, {result['drafts_deleted']} drafts, "
        f"{result['sends_deleted']} sends",
    )
