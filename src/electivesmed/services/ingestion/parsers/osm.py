"""Parser for OpenStreetMap hospitals via the Overpass API (worldwide)."""

from ....models.entities import Hospital
from ....models.enums import SourceType

DEFAULT_URL = "https://overpass-api.de/api/interpreter"
_SELECTOR = 'node["amenity"="hospital"]'


def build_query(entry) -> str:
    if entry.query:
        return entry.query
    if entry.country:
        return (
            "[out:json][timeout:60];"
            f'area["ISO3166-1"="{entry.country}"][admin_level=2]->.searchArea;'
            f"{_SELECTOR}(area.searchArea);"
            "out tags center;"
        )
    return f"[out:json][timeout:60];{_SELECTOR};out tags center;"


def parse_osm(http, entry, limit: int) -> list[Hospital]:
    payload = http.request_json(
        entry.url or DEFAULT_URL,
        method="POST",
        data={"data": build_query(entry)},
    )

    hospitals: list[Hospital] = []
    for element in payload.get("elements", []):
        if len(hospitals) >= limit:
            break
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue
        hospitals.append(
            Hospital(
                name=name,
                city=tags.get("addr:city") or None,
                state=tags.get("addr:state") or None,
                country=tags.get("addr:country") or entry.country or "",
                website=tags.get("website") or tags.get("contact:website") or None,
                hospital_type=tags.get("healthcare") or "Hospital",
                source_type=SourceType.OSM_OVERPASS,
                source_url=(
                    f"https://www.openstreetmap.org/{element.get('type', 'node')}/"
                    f"{element.get('id', '')}"
                ),
            )
        )
    return hospitals
