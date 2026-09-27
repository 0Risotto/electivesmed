from electivesmed.components.email_style import EmailStyleChecker

from tests import constants as C

checker = EmailStyleChecker()


def _has(violations, needle):
    return any(needle in violation for violation in violations)


def test_flags_em_dash():
    assert _has(checker.violations("Hello \u2014 quick note"), "em dash")


def test_flags_en_dash():
    assert _has(checker.violations("2019 \u2013 2024"), "en dash")


def test_flags_double_hyphen():
    assert _has(checker.violations("Hello -- quick note"), "double hyphen")


def test_flags_exclamation_mark():
    assert _has(checker.violations("Great news!"), "exclamation mark")


def test_flags_emoji():
    assert _has(checker.violations("Hello \U0001f600"), "emoji")


def test_flags_banned_word_with_suffixes():
    for text in (
        "We leverage data",
        "leveraging data",
        "seamlessly integrate",
        "streamlined process",
        "catalyzing growth",
        "showcasing results",
        "nestled downtown",
        "boasts a team",
    ):
        assert _has(checker.violations(text), "AI-typical words"), text


def test_flags_banned_phrases():
    assert _has(checker.violations("I hope this email finds you well."), "AI-typical phrases")
    assert _has(checker.violations("We can dive into that later."), "AI-typical phrases")


def test_clean_professional_copy_passes():
    assert checker.violations(C.CLEAN_BODY) == []
