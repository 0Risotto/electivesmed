"""Request dependencies for the web client: container, runner, auth, origin."""

from urllib.parse import quote

from fastapi import HTTPException, Request

from ...components import security


class AuthRequired(Exception):
    """Raised when a request needs a valid session; handled with a redirect."""


def get_container(request: Request):
    return request.app.state.container


def get_runner(request: Request):
    return request.app.state.runner


def current_username(request: Request) -> str | None:
    token = request.cookies.get("el_session", "")
    if not token:
        return None
    secret = security.load_session_key()
    return security.read_session_token(token, secret)


def require_user(request: Request) -> str:
    container = get_container(request)
    if not container.settings.web.require_login:
        request.state.username = "local"
        return "local"
    if container.dao.count_users() == 0:
        raise AuthRequired()
    username = current_username(request)
    if username is None or container.dao.find_user(username) is None:
        raise AuthRequired()
    request.state.username = username
    return username


def check_origin(request: Request) -> None:
    """Lightweight CSRF guard for state-changing requests."""
    origin = request.headers.get("origin")
    if not origin:
        return
    host = request.headers.get("host", "")
    if origin.rstrip("/") not in {f"http://{host}", f"https://{host}"}:
        raise HTTPException(status_code=403, detail="cross-origin request rejected")


def redirect_to_login(request: Request) -> "RedirectResponse":  # type: ignore[name-defined]
    from fastapi.responses import RedirectResponse

    target = request.url.path
    return RedirectResponse(f"/login?next={quote(target)}", status_code=303)
