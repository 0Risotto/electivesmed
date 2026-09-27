from electivesmed.models.enums import SourceType
from electivesmed.services.ingestion.parsers.cms import parse_cms_csv

from tests.fakes import FakeFetch


def test_parse_cms_csv(cms_csv, entry):
    source = entry(name="cms", type="csv", url="http://cms.test", country="US")

    hospitals = parse_cms_csv(FakeFetch(data=cms_csv), source, limit=10)

    assert len(hospitals) == 2
    first = hospitals[0]
    assert first.name == "Southeast Health Medical Center"
    assert first.city == "DOTHAN"
    assert first.state == "AL"
    assert first.country == "US"
    assert first.hospital_type == "Acute Care Hospitals"
    assert first.ownership.startswith("Government")
    assert first.source_type is SourceType.CMS_DATASET
    assert first.source_url == "http://cms.test"


def test_parse_cms_csv_respects_limit(cms_csv, entry):
    hospitals = parse_cms_csv(FakeFetch(data=cms_csv), entry(name="cms"), limit=1)

    assert len(hospitals) == 1


def test_parse_cms_csv_skips_rows_without_name(entry):
    raw = b'"Facility Name",City/Town\n,Nowhere\n'

    hospitals = parse_cms_csv(FakeFetch(data=raw), entry(name="cms"), limit=10)

    assert hospitals == []
