from hospital_outreach.models.values import EmailAddress, FitScore
from hospital_outreach.utils.email import email_domain
from hospital_outreach.utils.html import html_to_text
from hospital_outreach.utils.json import extract_json
from hospital_outreach.utils.text import word_count


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_extract_json_list_is_wrapped():
    assert extract_json('[{"id": 1}]') == {"items": [{"id": 1}]}


def test_email_address_validation():
    assert EmailAddress(value="A.B@Hospital.ORG").value == "a.b@hospital.org"
    for bad in ("not-an-email", "a@b", "a b@c.org"):
        try:
            EmailAddress(value=bad)
            raise AssertionError(f"should have rejected {bad!r}")
        except ValueError:
            pass


def test_fit_score_clamps():
    assert FitScore(score=1.5).score == 1.0
    assert FitScore(score=-0.4).score == 0.0


def test_html_to_text():
    text = html_to_text(
        "<html><head><style>x{}</style></head><body><h1>Hello</h1>"
        "<p>World &amp; friends</p><script>evil()</script></body></html>"
    )
    assert "Hello" in text
    assert "World & friends" in text
    assert "evil" not in text
    assert word_count("one two   three") == 3
    assert email_domain("Jane.Doe@Hospital.ORG") == "hospital.org"
