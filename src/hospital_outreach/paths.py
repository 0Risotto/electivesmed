"""Resolved filesystem locations (runtime values, not constants)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB_PATH = REPO_ROOT / "data" / "outreach.db"
DEFAULT_PROFILE_PATH = REPO_ROOT / "config" / "profile.yaml"
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"
CACHE_DIR = REPO_ROOT / "data" / "cache"
EXPORT_DIR = REPO_ROOT / "data" / "exports"
ENV_PATH = REPO_ROOT / ".env"
