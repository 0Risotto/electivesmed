"""Parser for generic hospital CSV files (any country, local file or URL)."""

import csv
import io
from pathlib import Path

from ....models.entities import Hospital
from ....models.enums import SourceType
from .common import first_value, normalized_row

NAME_KEYS = ("name", "facility_name", "hospital_name", "hospital", "organisation", "organization")
CITY_KEYS = ("city", "city_town", "citytown", "town", "municipality")
STATE_KEYS = ("state", "region", "province", "county")
COUNTRY_KEYS = ("country", "country_code", "iso_country")
TYPE_KEYS = ("hospital_type", "type", "category")
OWNERSHIP_KEYS = ("ownership", "operator", "sector")
WEBSITE_KEYS = ("website", "url", "homepage", "site")


def _read_text(http, entry) -> str:
    if entry.path:
        return Path(entry.path).read_text(encoding="utf-8-sig")
    raw = http.fetch_bytes(entry.url)
    return raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else str(raw)


def parse_generic_csv(http, entry, limit: int) -> list[Hospital]:
    text = _read_text(http, entry)
    hospitals: list[Hospital] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw_row in reader:
        if len(hospitals) >= limit:
            break
        row = normalized_row(raw_row)
        name = first_value(row, NAME_KEYS)
        if not name:
            continue
        hospitals.append(
            Hospital(
                name=name,
                city=first_value(row, CITY_KEYS) or None,
                state=first_value(row, STATE_KEYS) or None,
                country=first_value(row, COUNTRY_KEYS) or entry.country or "",
                website=first_value(row, WEBSITE_KEYS) or None,
                hospital_type=first_value(row, TYPE_KEYS) or None,
                ownership=first_value(row, OWNERSHIP_KEYS) or None,
                source_type=SourceType.FILE if entry.path else SourceType.CSV,
                source_url=entry.url or entry.path,
            )
        )
    return hospitals
