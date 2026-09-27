from electivesmed.models.config import SourceEntry
from electivesmed.models.enums import SourceType
from electivesmed.services.ingestion.registry import (
    DEFAULT_CMS_URL,
    builtin_sources,
    configured_entries,
    get_entry,
)


def test_configured_entries_read_from_settings(container):
    container.settings.sources.entries = [
        SourceEntry(name="cms", type="cms", url="http://cms.test"),
        SourceEntry(name="osm", type="overpass", url="http://osm.test"),
        SourceEntry(name="wd", type="sparql", url="http://wd.test"),
    ]

    names = [entry.name for entry in configured_entries(container.settings)]
    assert names == ["cms", "osm", "wd"]

    sources = builtin_sources(container.settings)
    assert [source.type for source in sources] == [
        SourceType.CMS_DATASET,
        SourceType.OSM_OVERPASS,
        SourceType.WIKIDATA,
    ]
    assert sources[1].uri == "http://osm.test"


def test_disabled_entries_are_filtered(container):
    container.settings.sources.entries = [
        SourceEntry(name="cms", type="csv", url="http://cms.test"),
        SourceEntry(name="off", type="csv", url="http://off.test", enabled=False),
    ]

    assert [entry.name for entry in configured_entries(container.settings)] == ["cms"]


def test_legacy_cms_url_fallback(container):
    container.settings.sources.entries = []
    container.settings.sources.cms_url = "http://legacy.test/hospitals.csv"

    entries = configured_entries(container.settings)

    assert len(entries) == 1
    assert entries[0].name == "cms"
    assert entries[0].url == "http://legacy.test/hospitals.csv"
    assert entries[0].country == "US"


def test_legacy_fallback_uses_default_url(container):
    container.settings.sources.entries = []
    container.settings.sources.cms_url = ""

    assert configured_entries(container.settings)[0].url == DEFAULT_CMS_URL


def test_get_entry_is_case_insensitive(container):
    container.settings.sources.entries = [
        SourceEntry(name="charite", type="file", path="data/charite.csv")
    ]

    assert get_entry(container.settings, "  CHARITE ").name == "charite"
    assert get_entry(container.settings, "missing") is None


def test_builtin_sources_use_path_when_url_empty(container):
    container.settings.sources.entries = [
        SourceEntry(name="local", type="file", path="data/local.csv")
    ]

    assert builtin_sources(container.settings)[0].uri == "data/local.csv"
