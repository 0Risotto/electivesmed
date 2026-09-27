"""Component: professional email style rules. Pure text scanning, no I/O.

Enforces: no em/en dashes, no exclamation marks, no emoji, no AI-typical
words or corporate filler phrases.
"""

import re

from ..compliance import BANNED_PHRASES, BANNED_PUNCTUATION, BANNED_WORDS

_EMOJI_RE = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")


def _word_variants(word: str) -> set[str]:
    """All inflections the scanner should catch, including e-drop forms."""
    variants = {word, word + "s", word + "es", word + "ed", word + "d", word + "ing", word + "ly"}
    if word.endswith("e"):
        stem = word[:-1]
        variants.update({stem + "ing", stem + "ed"})
    if word.endswith("y"):
        variants.add(word[:-1] + "ies")
    return variants


_ALL_WORD_VARIANTS = sorted(
    {variant for word in BANNED_WORDS for variant in _word_variants(word)},
    key=len,
    reverse=True,
)
_BANNED_WORD_RE = re.compile(
    r"\b(?:" + "|".join(map(re.escape, _ALL_WORD_VARIANTS)) + r")\b",
    re.IGNORECASE,
)
_BANNED_PHRASE_RE = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, BANNED_PHRASES), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


class EmailStyleChecker:
    def violations(self, text: str) -> list[str]:
        """Return human-readable style violations found in the text."""
        found: list[str] = []

        for char, label in BANNED_PUNCTUATION.items():
            if char in text:
                found.append(f"{label} present")

        if "!" in text:
            found.append("exclamation mark present")
        if _EMOJI_RE.search(text):
            found.append("emoji present")

        words = sorted({m.group(0).lower() for m in _BANNED_WORD_RE.finditer(text)})
        if words:
            found.append("AI-typical words: " + ", ".join(words[:8]))

        phrases = sorted({m.group(0).lower() for m in _BANNED_PHRASE_RE.finditer(text)})
        if phrases:
            found.append("AI-typical phrases: " + ", ".join(phrases[:5]))

        return found
