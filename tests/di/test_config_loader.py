import pytest

from electivesmed.di.config_loader import provide_profile, provide_settings
from electivesmed.errors import ConfigError

from tests import constants as C


def test_settings_defaults_when_file_missing(tmp_path):
    settings = provide_settings(tmp_path / "missing.yaml")

    assert settings.limits.daily_send_cap == 50
    assert settings.model.chat == "deepseek/deepseek-chat"


def test_settings_read_from_yaml(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "limits:\n  daily_send_cap: 5\nsources:\n  cms_url: http://configured.test\n"
    )

    settings = provide_settings(path)

    assert settings.limits.daily_send_cap == 5
    assert settings.sources.cms_url == "http://configured.test"


def test_settings_env_path_override(tmp_path, monkeypatch):
    path = tmp_path / "custom-settings.yaml"
    path.write_text("limits:\n  daily_send_cap: 7\n")
    monkeypatch.setenv("EL_SETTINGS_PATH", str(path))

    assert provide_settings().limits.daily_send_cap == 7


def test_settings_rejects_non_mapping_yaml(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("- just\n- a\n- list\n")

    with pytest.raises(ConfigError):
        provide_settings(path)


def test_profile_defaults_when_file_missing(tmp_path):
    profile = provide_profile(tmp_path / "missing.yaml")

    assert profile.tone == "professional, warm, concise"
    assert profile.language == "en"


def test_profile_read_from_yaml(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(f"goal: {C.CAMPAIGN_GOAL}\nspecialties:\n  - Cardiology\n")

    profile = provide_profile(path)

    assert profile.goal == C.CAMPAIGN_GOAL
    assert profile.specialties == ["Cardiology"]


def test_profile_env_path_override(tmp_path, monkeypatch):
    path = tmp_path / "custom-profile.yaml"
    path.write_text(f"goal: {C.CAMPAIGN_GOAL}\n")
    monkeypatch.setenv("EL_PROFILE_PATH", str(path))

    assert provide_profile().goal == C.CAMPAIGN_GOAL
