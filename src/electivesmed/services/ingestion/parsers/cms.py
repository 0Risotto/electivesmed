"""Parser for the CMS Hospital General Information CSV (US)."""

import csv
import io

from ....models.entities import Hospital
from ....models.enums import SourceType
from .common import normalized_row


def parse_cms_csv(http, entry, limit: int) -> list[Hospital]:
    raw = http.fetch_bytes(entry.url or entry.path)
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else str(raw)

    hospitals: list[Hospital] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw_row in reader:
        if len(hospitals) >= limit:
            break
        row = normalized_row(raw_row)
        name = row.get("facility_name", "")
        if not name:
            continue
        hospitals.append(
            Hospital(
                name=name.title() if name.isupper() else name,
                city=row.get("city_town") or row.get("citytown") or None,
                state=row.get("state") or None,
                country=entry.country or "US",
                hospital_type=row.get("hospital_type") or None,
                ownership=row.get("hospital_ownership") or None,
                source_type=SourceType.CMS_DATASET,
                source_url=entry.url or entry.path,
            )
        )
    return hospitals
