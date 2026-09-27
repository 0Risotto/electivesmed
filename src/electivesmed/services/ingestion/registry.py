"""Source registry: turns settings into configured hospital data sources."""

from ...models.config import Settings, SourceEntry
from ...models.entities import Source
from ...models.enums import SourceType

DEFAULT_CMS_URL = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0/download?format=csv"
)

_TYPE_MAP = {
    "cms": SourceType.CMS_DATASET,
    "cms_dataset": SourceType.CMS_DATASET,
    "csv": SourceType.CSV,
    "file": SourceType.FILE,
    "overpass": SourceType.OSM_OVERPASS,
    "osm": SourceType.OSM_OVERPASS,
    "sparql": SourceType.WIKIDATA,
    "wikidata": SourceType.WIKIDATA,
}


def configured_entries(settings: Settings) -> list[SourceEntry]:
    """All enabled source entries; falls back to the legacy CMS URL."""
    if settings.sources.entries:
        return [entry for entry in settings.sources.entries if entry.enabled]
    return [
        SourceEntry(
            name="cms",
            type="csv",
            parser="cms_hospitals",
            url=settings.sources.cms_url or DEFAULT_CMS_URL,
            country="US",
            description="CMS Hospital General Information (US, public domain)",
        )
    ]


def get_entry(settings: Settings, name: str) -> SourceEntry | None:
    wanted = name.strip().lower()
    return next(
        (entry for entry in configured_entries(settings) if entry.name.lower() == wanted),
        None,
    )


def builtin_sources(settings: Settings) -> list[Source]:
    return [
        Source(
            type=_TYPE_MAP.get(entry.type.lower(), SourceType.CSV),
            name=entry.name,
            uri=entry.url or entry.path,
            description=entry.description,
        )
        for entry in configured_entries(settings)
    ]
