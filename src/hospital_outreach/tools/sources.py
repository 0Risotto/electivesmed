"""Thin tools over the ingestion activity."""

from strands import tool

from ..services.ingestion import builtin_sources, fetch_source as fetch_source_activity


def build(container) -> list:
    @tool
    def list_sources() -> list[dict]:
        """List configured hospital data sources available for scouting."""
        return [s.model_dump(mode="json") for s in builtin_sources(container.settings)]

    @tool
    def fetch_source(source_name: str, limit: int = 200) -> dict:
        """Download a configured bulk dataset and store its hospital records.

        Args:
            source_name: Name from list_sources (currently: "cms").
            limit: Maximum hospital rows to ingest.
        """
        return fetch_source_activity(container, source_name, limit)

    return [list_sources, fetch_source]
