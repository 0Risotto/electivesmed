"""Parser for hospitals from Wikidata via SPARQL (worldwide)."""

from ....models.entities import Hospital
from ....models.enums import SourceType

DEFAULT_URL = "https://query.wikidata.org/sparql"


def build_query(limit: int) -> str:
    return f"""
SELECT ?item ?itemLabel ?website ?countryCode ?cityLabel WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q16917 .
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  OPTIONAL {{ ?item wdt:P17 ?country. ?country wdt:P297 ?countryCode. }}
  OPTIONAL {{ ?item wdt:P131 ?city. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""


def _value(binding: dict, key: str) -> str:
    return binding.get(key, {}).get("value", "")


def parse_wikidata(http, entry, limit: int) -> list[Hospital]:
    payload = http.request_json(
        entry.url or DEFAULT_URL,
        params={"query": entry.query or build_query(limit), "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
    )

    hospitals: list[Hospital] = []
    for binding in payload.get("results", {}).get("bindings", []):
        if len(hospitals) >= limit:
            break
        item = _value(binding, "item")
        name = _value(binding, "itemLabel")
        if not name or name == item.rsplit("/", 1)[-1]:
            continue  # unlabeled entity (label rendered as its QID)
        hospitals.append(
            Hospital(
                name=name,
                city=_value(binding, "cityLabel") or None,
                country=_value(binding, "countryCode") or entry.country or "",
                website=_value(binding, "website") or None,
                source_type=SourceType.WIKIDATA,
                source_url=item,
            )
        )
    return hospitals
