from electivesmed.models.enums import SourceType
from electivesmed.services.ingestion.parsers.generic_csv import parse_generic_csv

from tests.fakes import FakeFetch


def test_parse_local_file(generic_hospitals_csv, entry):
    source = entry(name="local", type="file", path=str(generic_hospitals_csv))

    hospitals = parse_generic_csv(FakeFetch(), source, limit=10)

    assert len(hospitals) == 3
    charite = hospitals[0]
    assert charite.name.startswith("Charité")
    assert charite.city == "Berlin"
    assert charite.country == "DE"
    assert charite.website == "https://www.charite.de"
    assert charite.hospital_type == "University Hospital"
    assert charite.source_type is SourceType.FILE
    assert charite.source_url == str(generic_hospitals_csv)
    assert {hospital.country for hospital in hospitals} == {"DE", "GB", "CA"}


def test_parse_from_url_uses_entry_country(entry):
    raw = b"facility_name,city\nClinique X,Paris\n,Nowhere\n"
    source = entry(name="fr", type="csv", url="http://fr.test", country="FR")

    hospitals = parse_generic_csv(FakeFetch(data=raw), source, limit=10)

    assert len(hospitals) == 1
    assert hospitals[0].country == "FR"
    assert hospitals[0].source_type is SourceType.CSV


def test_parse_generic_csv_respects_limit(generic_hospitals_csv, entry):
    source = entry(name="local", type="file", path=str(generic_hospitals_csv))

    assert len(parse_generic_csv(FakeFetch(), source, limit=1)) == 1
