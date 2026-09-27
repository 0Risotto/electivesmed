"""Atomic, permission-safe writers for .env and config YAML files."""

import os
import tempfile
from pathlib import Path

import yaml

from ..errors import ConfigWriteError


def _atomic_write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(text)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except OSError as exc:
        raise ConfigWriteError(f"failed to write {path}: {exc}") from exc
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_env_values(updates: dict[str, str | None], path: Path) -> Path:
    """Update/insert keys (None removes); preserves comments, order, and 0600 perms."""
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            value = remaining.pop(key)
            if value is None:
                continue
            out.append(f"{key}={value}")
        else:
            out.append(line)
    for key, value in remaining.items():
        if value is not None:
            out.append(f"{key}={value}")
    _atomic_write(path, "\n".join(out).rstrip("\n") + "\n", mode=0o600)
    return path


def _deep_merge(base: dict, updates: dict) -> dict:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def write_yaml_values(path: Path, updates: dict) -> Path:
    """Deep-merge values into a YAML file, keeping a one-deep .bak backup."""
    existing: dict = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ConfigWriteError(f"{path} must contain a YAML mapping")
        existing = loaded
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(path.read_text())
    merged = _deep_merge(existing, updates)
    _atomic_write(path, yaml.safe_dump(merged, sort_keys=False, allow_unicode=True), mode=0o644)
    return path
