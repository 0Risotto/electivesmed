"""Thin tools over the HTTP accessor for public page fetching."""

from strands import tool

from ..constants.limits import MAX_HTML_TEXT_CHARS
from ..utils.html import html_to_text


def fetch_page_text(container, url: str) -> str:
    html = container.http.fetch_text(url)
    text = html_to_text(html, MAX_HTML_TEXT_CHARS)
    return text or "[page contained no extractable text]"


def build(container) -> list:
    @tool
    def fetch_page(url: str) -> str:
        """Fetch a public web page and return its visible text.

        The accessor respects robots.txt, throttles per host, and caches responses.
        Use this for staff directories, leadership pages, and department pages.
        """
        return fetch_page_text(container, url)

    @tool
    def fetch_staff_page(hospital: str, url: str) -> str:
        """Fetch a public staff/leadership directory page and return its visible text.

        Args:
            hospital: Hospital name the page belongs to (for logging context).
            url: Public page URL.
        """
        return fetch_page_text(container, url)

    return [fetch_page, fetch_staff_page]
