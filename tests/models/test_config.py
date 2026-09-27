from electivesmed.models.config import Profile, Settings

from tests import constants as C


def test_settings_defaults():
    settings = Settings()

    assert settings.limits.daily_send_cap == 50
    assert settings.limits.per_domain_cap == 2
    assert settings.sending.dry_run_default is True
    assert settings.sending.include_opt_out is True
    assert settings.model.chat == "deepseek/deepseek-chat"
    assert settings.smtp.port == 587
    assert settings.sources.cms_url == ""


def test_profile_defaults():
    profile = Profile()

    assert profile.tone == "professional, warm, concise"
    assert profile.language == "en"
    assert profile.specialties == []
    assert profile.avoid == []


def test_profile_accepts_values():
    profile = Profile(goal=C.CAMPAIGN_GOAL, specialties=["Cardiology"], locations=[C.HOSPITAL_CITY])

    assert profile.goal == C.CAMPAIGN_GOAL
    assert profile.specialties == ["Cardiology"]
    assert profile.locations == [C.HOSPITAL_CITY]


def test_compliance_defaults():
    compliance = Settings().compliance

    assert compliance.eu_policy == "block"
    assert compliance.us_policy == "block"
    assert compliance.retention_days == 730
    assert compliance.jurisdiction_overrides == {}


def test_sending_window_defaults():
    sending = Settings().sending

    assert sending.window_enabled is True
    assert sending.window_days == [1, 2, 3]
    assert (sending.window_start, sending.window_end) == ("09:00", "17:00")


def test_sources_default_to_empty_entries():
    sources = Settings().sources

    assert sources.entries == []
    assert sources.cms_url == ""


def test_source_entry_defaults():
    from electivesmed.models.config import SourceEntry

    entry = SourceEntry(name="osm", type="overpass")

    assert entry.enabled is True
    assert entry.parser == ""
    assert entry.country == ""


def test_attachments_and_web_defaults():
    settings = Settings()

    assert settings.attachments.defaults == []
    assert settings.attachments.max_files == 5
    assert settings.attachments.max_file_mb == 10
    assert settings.attachments.max_total_mb == 20
    assert settings.web.require_login is True


def test_web_lockout_defaults():
    web = Settings().web

    assert web.login_attempts == 10
    assert web.lockout_seconds == 120
