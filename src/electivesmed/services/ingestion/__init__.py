"""Ingestion activities: configurable data sources and their parsers."""

from .registry import DEFAULT_CMS_URL, builtin_sources, configured_entries, get_entry
from .service import fetch_source

__all__ = [
    "DEFAULT_CMS_URL",
    "builtin_sources",
    "configured_entries",
    "get_entry",
    "fetch_source",
]
