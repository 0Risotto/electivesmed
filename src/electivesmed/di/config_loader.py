"""Load Settings and Profile from config/*.yaml."""

import os
from pathlib import Path

import yaml

from ..errors import ConfigError
from ..models.config import Profile, Settings
from ..paths import DEFAULT_PROFILE_PATH, DEFAULT_SETTINGS_PATH


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")
    return data


def settings_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else Path(
        os.environ.get("EL_SETTINGS_PATH", DEFAULT_SETTINGS_PATH)
    )


def profile_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else Path(
        os.environ.get("EL_PROFILE_PATH", DEFAULT_PROFILE_PATH)
    )


def provide_settings(path: str | Path | None = None) -> Settings:
    return Settings.model_validate(_read_yaml(settings_path(path)))


def provide_profile(path: str | Path | None = None) -> Profile:
    return Profile.model_validate(_read_yaml(profile_path(path)))
