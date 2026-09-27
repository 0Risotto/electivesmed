"""Region data: EU/EEA/UK membership, timezone lookup, jurisdiction rule profiles."""

EU_EEA_UK = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        "IS",
        "LI",
        "NO",
        "GB",
    }
)

UNITED_STATES = frozenset({"US"})

COUNTRY_TIMEZONES = {
    "US": "America/New_York",
    "CA": "America/Toronto",
    "MX": "America/Mexico_City",
    "BR": "America/Sao_Paulo",
    "AR": "America/Argentina/Buenos_Aires",
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "ES": "Europe/Madrid",
    "IT": "Europe/Rome",
    "NL": "Europe/Amsterdam",
    "BE": "Europe/Brussels",
    "CH": "Europe/Zurich",
    "AT": "Europe/Vienna",
    "PL": "Europe/Warsaw",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "PT": "Europe/Lisbon",
    "GR": "Europe/Athens",
    "CZ": "Europe/Prague",
    "RO": "Europe/Bucharest",
    "HU": "Europe/Budapest",
    "TR": "Europe/Istanbul",
    "IL": "Asia/Jerusalem",
    "AE": "Asia/Dubai",
    "IN": "Asia/Kolkata",
    "SG": "Asia/Singapore",
    "CN": "Asia/Shanghai",
    "JP": "Asia/Tokyo",
    "ZA": "Africa/Johannesburg",
    "AU": "Australia/Sydney",
    "NZ": "Pacific/Auckland",
}
DEFAULT_TIMEZONE = "UTC"

JURISDICTION_EU = "eu"
JURISDICTION_US = "us"
JURISDICTION_DEFAULT = "default"

_PROFILES: dict[str, dict[str, bool]] = {
    JURISDICTION_EU: {"requires_lawful_basis": True, "requires_postal_address": False},
    JURISDICTION_US: {"requires_lawful_basis": False, "requires_postal_address": True},
    JURISDICTION_DEFAULT: {"requires_lawful_basis": False, "requires_postal_address": False},
}


def normalize_country(country: str | None) -> str:
    return (country or "").strip().upper()


def jurisdiction_for(country: str | None) -> str:
    code = normalize_country(country)
    if code in EU_EEA_UK:
        return JURISDICTION_EU
    if code in UNITED_STATES:
        return JURISDICTION_US
    return JURISDICTION_DEFAULT


def profile_for(country: str | None, overrides: dict | None = None) -> dict[str, bool]:
    """Rule profile for a recipient country, with optional per-country overrides."""
    profile = dict(_PROFILES[jurisdiction_for(country)])
    override = (overrides or {}).get(normalize_country(country))
    if override:
        profile.update(override)
    return profile


def timezone_for(country: str | None) -> str:
    return COUNTRY_TIMEZONES.get(normalize_country(country), DEFAULT_TIMEZONE)
