"""Ingestion activity: fetch a configured source and persist its hospitals."""

from . import registry
from .parsers import PARSERS


def fetch_source(container, source_name: str, limit: int = 200) -> dict:
    entry = registry.get_entry(container.settings, source_name)
    if entry is None:
        known = [source.name for source in registry.configured_entries(container.settings)]
        return {"error": f"unknown source {source_name!r}", "known_sources": known}

    parser_key = (entry.parser or entry.type).lower()
    parser = PARSERS.get(parser_key)
    if parser is None:
        return {"error": f"no parser registered for {parser_key!r}", "source": entry.name}

    hospitals = parser(container.http, entry, limit)[:limit]
    for hospital in hospitals:
        container.dao.upsert_hospital(hospital)
    return {
        "source": entry.name,
        "country": entry.country or None,
        "hospitals_added_or_updated": len(hospitals),
        "source_url": entry.url or entry.path,
    }
