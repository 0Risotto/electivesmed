"""Source parsers, keyed by parser name or source type."""

from .cms import parse_cms_csv
from .generic_csv import parse_generic_csv
from .osm import parse_osm
from .wikidata import parse_wikidata

PARSERS = {
    "cms": parse_cms_csv,
    "cms_hospitals": parse_cms_csv,
    "csv": parse_generic_csv,
    "generic_csv": parse_generic_csv,
    "file": parse_generic_csv,
    "overpass": parse_osm,
    "osm": parse_osm,
    "sparql": parse_wikidata,
    "wikidata": parse_wikidata,
}

__all__ = [
    "PARSERS",
    "parse_cms_csv",
    "parse_generic_csv",
    "parse_osm",
    "parse_wikidata",
]
