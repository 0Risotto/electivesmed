from electivesmed.utils.email import email_domain
from electivesmed.utils.text import normalize_whitespace, word_count


def test_normalize_whitespace():
    assert normalize_whitespace("  one   two  ") == "one two"
    assert normalize_whitespace("line\nbreak") == "line break"


def test_word_count():
    assert word_count("one two   three") == 3
    assert word_count("") == 0


def test_email_domain():
    assert email_domain("Jane.Doe@Hospital.ORG") == "hospital.org"
    assert email_domain("not-an-email") == ""
