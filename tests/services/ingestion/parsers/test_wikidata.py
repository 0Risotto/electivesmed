from electivesmed.models.enums import SourceType
from electivesmed.services.ingestion.parsers.wikidata import (
    DEFAULT_URL,
    build_query,
    parse_wikidata,
)

from tests.fakes import FakeFetch


def test_build_query_contains_limit():
    query = build_query(42)

    assert "LIMIT 42" in query
    assert "wd:Q16917" in query


def test_parse_wikidata_response(wikidata_response, entry):
    source = entry(name="wd", type="sparql", url="http://wd.test")

    hospitals = parse_wikidata(FakeFetch(json_response=wikidata_response), source, limit=10)

    assert len(hospitals) == 1
    hospital = hospitals[0]
    assert hospital.name == "Charité"
    assert hospital.city == "Berlin"
    assert hospital.country == "DE"
    assert hospital.website == "https://www.charite.de"
    assert hospital.source_type is SourceType.WIKIDATA
    assert hospital.source_url.endswith("Q4221")


def test_parse_wikidata_uses_default_url_and_entry_country(entry):
    source = entry(name="wd", type="sparql", country="FR")
    payload = {"results": {"bindings": [{"item": {"value": "http://x/Q1"}, "itemLabel": {"value": "H"}}]}}
    http = FakeFetch(json_response=payload)

    hospitals = parse_wikidata(http, source, limit=10)

    assert http.json_calls[0]["url"] == DEFAULT_URL
    assert hospitals[0].country == "FR"


def test_parse_wikidata_respects_limit(wikidata_response, entry):
    assert len(parse_wikidata(FakeFetch(json_response=wikidata_response), entry(name="wd"), 0)) == 0
