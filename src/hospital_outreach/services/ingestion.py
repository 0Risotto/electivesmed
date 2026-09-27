"""Activity: ingest hospitals from public data sources into storage."""

import csv
import io
import re

from ..models.entities import Hospital, Source
from ..models.enums import SourceType

DEFAULT_CMS_URL = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0/download?format=csv"
)


def builtin_sources(settings) -> list[Source]:
    return [
        Source(
            type=SourceType.CMS_DATASET,
            name="cms",
            uri=settings.sources.cms_url or DEFAULT_CMS_URL,
            description="CMS Hospital General Information (US, public domain)",
        ),
    ]


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def ingest_cms_csv(dao, raw: bytes, source_url: str, limit: int = 200) -> int:
    """Parse the CMS hospital CSV into Hospital records. Tolerant to column renames."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    added = 0
    for raw_row in reader:
        if added >= limit:
            break
        row = {_norm_key(key or ""): (value or "").strip() for key, value in raw_row.items()}
        name = row.get("facility_name") or ""
        if not name:
            continue
        hospital = Hospital(
            name=name if not name.isupper() else name.title(),
            city=row.get("city_town") or row.get("citytown") or None,
            state=row.get("state") or None,
            hospital_type=row.get("hospital_type") or None,
            ownership=row.get("hospital_ownership") or None,
            source_type=SourceType.CMS_DATASET,
            source_url=source_url,
        )
        dao.upsert_hospital(hospital)
        added += 1
    return added


def fetch_source(container, source_name: str, limit: int = 200) -> dict:
    sources = {s.name: s for s in builtin_sources(container.settings)}
    source = sources.get(source_name.strip().lower())
    if source is None:
        return {"error": f"unknown source {source_name!r}", "known_sources": list(sources)}
    raw = container.http.fetch_bytes(source.uri)
    added = ingest_cms_csv(container.dao, raw, source.uri, limit)
    return {"source": source.name, "hospitals_added_or_updated": added, "source_url": source.uri}
