"""Sources: configured data sources and ingest actions."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from ....services.ingestion import configured_entries, fetch_source
from ..deps import get_container
from ..helpers import redirect_with_flash
from ..templating import templates

router = APIRouter(prefix="/sources")


@router.get("", response_class=HTMLResponse)
def list_sources(request: Request, container=Depends(get_container)):
    entries = configured_entries(container.settings)
    return templates.TemplateResponse(
        request, "sources.html", {"entries": entries}
    )


@router.post("/ingest")
def ingest(
    request: Request,
    name: str = Form(...),
    limit: int = Form(50),
    container=Depends(get_container),
):
    result = fetch_source(container, name, limit)
    if "error" in result:
        return redirect_with_flash("/sources", f"ingest failed: {result['error']}")
    return redirect_with_flash(
        "/sources",
        f"ingested {result['hospitals_added_or_updated']} hospitals from {result['source']}",
    )
