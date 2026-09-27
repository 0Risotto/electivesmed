from electivesmed.models.enums import SourceType
from electivesmed.services.ingestion.parsers.osm import (
    DEFAULT_URL,
    build_query,
    parse_osm,
)

from tests.fakes import FakeFetch


def test_build_query_scoped_to_country(entry):
    query = build_query(entry(country="DE"))

    assert 'area["ISO3166-1"="DE"]' in query
    assert 'node["amenity"="hospital"]' in query


def test_build_query_global(entry):
    query = build_query(entry())

    assert 'node["amenity"="hospital"]' in query
    assert "area" not in query


def test_build_query_custom_override(entry):
    assert build_query(entry(query="custom body")) == "custom body"


def test_parse_osm_response(osm_response, entry):
    source = entry(name="osm", type="overpass", url="http://osm.test")

    hospitals = parse_osm(FakeFetch(json_response=osm_response), source, limit=10)

    assert len(hospitals) == 2
    first = hospitals[0]
    assert first.name.startswith("Charité")
    assert first.city == "Berlin"
    assert first.country == "DE"
    assert first.website == "https://www.charite.de"
    assert first.hospital_type == "hospital"
    assert first.source_type is SourceType.OSM_OVERPASS
    assert first.source_url == "https://www.openstreetmap.org/node/1001"
    assert hospitals[1].website == "https://www.guysandstthomas.nhs.uk"


def test_parse_osm_uses_default_url_and_entry_country(osm_response, entry):
    source = entry(name="osm", type="overpass", country="FR")
    http = FakeFetch(json_response={"elements": [{"type": "node", "id": 7, "tags": {"name": "X"}}]})

    hospitals = parse_osm(http, source, limit=10)

    assert http.json_calls[0]["url"] == DEFAULT_URL
    assert hospitals[0].country == "FR"


def test_parse_osm_respects_limit(osm_response, entry):
    assert len(parse_osm(FakeFetch(json_response=osm_response), entry(name="osm"), limit=1)) == 1
