"""Shared helpers for source parsers."""

import re


def norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (key or "").strip().lower()).strip("_")


def cell(value: object) -> str:
    """Normalize a table cell; extra CSV columns arrive as lists."""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def normalized_row(raw_row: dict) -> dict[str, str]:
    return {norm_key(key or ""): cell(value) for key, value in raw_row.items()}


def first_value(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return ""
