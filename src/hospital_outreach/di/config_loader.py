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


def provide_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path else Path(
        os.environ.get("HO_SETTINGS_PATH", DEFAULT_SETTINGS_PATH)
    )
    return Settings.model_validate(_read_yaml(config_path))


def provide_profile(path: str | Path | None = None) -> Profile:
    config_path = Path(path) if path else Path(
        os.environ.get("HO_PROFILE_PATH", DEFAULT_PROFILE_PATH)
    )
    return Profile.model_validate(_read_yaml(config_path))
