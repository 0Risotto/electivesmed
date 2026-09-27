import electivesmed.utils.html as html_module
from electivesmed.utils.html import html_to_text


def test_html_to_text_strips_scripts_and_preserves_text():
    html = (
        "<html><head><style>x{}</style></head><body>"
        "<h1>Hello</h1><p>World &amp; friends</p>"
        "<script>evil()</script></body></html>"
    )

    text = html_to_text(html)

    assert "Hello" in text
    assert "World & friends" in text
    assert "evil" not in text


def test_html_to_text_truncates():
    assert html_to_text("<p>abcdefghij</p>", max_chars=5) == "abcde"


def test_html_to_text_survives_parser_errors(monkeypatch):
    class BrokenParser:
        chunks: list = []
        _skip_depth = 0

        def feed(self, data):
            raise RuntimeError("parser exploded")

    monkeypatch.setattr(html_module, "_TextExtractor", BrokenParser)

    assert html_to_text("<p>text</p>") == ""
