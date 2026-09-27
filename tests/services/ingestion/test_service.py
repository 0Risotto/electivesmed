from electivesmed.models.config import SourceEntry
from electivesmed.services.ingestion.service import fetch_source


def test_fetch_source_rejects_unknown_name(container, fake_fetch):
    result = fetch_source(container, "nope")

    assert "error" in result
    assert "cms" in result["known_sources"]


def test_fetch_source_rejects_unknown_parser(container, entry):
    container.settings.sources.entries = [entry(name="odd", parser="does-not-exist")]

    result = fetch_source(container, "odd")

    assert result["error"].startswith("no parser registered")


def test_fetch_source_ingests_cms(container, fake_fetch):
    result = fetch_source(container, "cms", limit=10)

    assert result["source"] == "cms"
    assert result["country"] == "US"
    assert result["hospitals_added_or_updated"] == 2
    assert container.dao.summary()["hospitals"] == 2


def test_fetch_source_ingests_local_csv(container, entry, generic_hospitals_csv):
    container.settings.sources.entries = [
        entry(name="local", type="file", path=str(generic_hospitals_csv))
    ]

    result = fetch_source(container, "local", limit=10)

    assert result["hospitals_added_or_updated"] == 3
    hospitals = container.dao.find_hospitals()
    countries = {hospital.country for hospital in hospitals}
    assert countries == {"DE", "GB", "CA"}


def test_fetch_source_uses_entry_country_fallback(container, entry):
    container.settings.sources.entries = [
        entry(name="fr", type="csv", url="http://fr.test", country="FR")
    ]
    from tests.fakes import FakeFetch

    container.http = FakeFetch(data=b"name,city\nClinique,Paris\n")

    result = fetch_source(container, "fr", limit=10)

    assert result["country"] == "FR"
    assert container.dao.find_hospitals()[0].country == "FR"


def test_fetch_source_respects_limit(container, fake_fetch):
    result = fetch_source(container, "cms", limit=1)

    assert result["hospitals_added_or_updated"] == 1
    assert container.dao.summary()["hospitals"] == 1


def test_fetch_source_without_url_or_path(container, entry, fake_fetch):
    container.settings.sources.entries = [entry(name="empty", type="csv")]

    result = fetch_source(container, "empty")

    assert result["source_url"] == ""
    assert result["hospitals_added_or_updated"] == 2  # fake fetch serves the CMS sample
