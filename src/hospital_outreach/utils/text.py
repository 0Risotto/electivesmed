"""Plain-text helpers."""

import re


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def word_count(text: str) -> int:
    return len(normalize_whitespace(text).split())
