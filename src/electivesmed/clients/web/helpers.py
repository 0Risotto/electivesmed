"""Small web-client helpers."""

from urllib.parse import quote

from fastapi.responses import RedirectResponse


def redirect_with_flash(url: str, message: str) -> RedirectResponse:
    separator = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separator}flash={quote(message)}", status_code=303)
