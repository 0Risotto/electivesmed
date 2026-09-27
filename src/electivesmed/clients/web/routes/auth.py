"""Authentication: first-run setup, login, logout."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ....components import security
from ....errors import SecurityError
from ..deps import get_container
from ..helpers import redirect_with_flash
from ..templating import templates

router = APIRouter()


def _set_session(response, username: str) -> None:
    secret = security.load_session_key()
    token = security.create_session_token(username, secret)
    response.set_cookie(
        "el_session",
        token,
        max_age=security.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, container=Depends(get_container)):
    if container.dao.count_users() > 0:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "setup.html", {})


@router.post("/setup")
def setup_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    container=Depends(get_container),
):
    if container.dao.count_users() > 0:
        return RedirectResponse("/login", status_code=303)
    username = username.strip()
    if not username:
        return redirect_with_flash("/setup", "username is required")
    if password != confirm:
        return redirect_with_flash("/setup", "passwords do not match")
    try:
        security.validate_password(password, username)
    except SecurityError as exc:
        return redirect_with_flash("/setup", str(exc))
    password_hash = security.hash_password(password)
    container.dao.create_user(username, password_hash)
    response = RedirectResponse("/", status_code=303)
    _set_session(response, username)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, container=Depends(get_container)):
    if container.dao.count_users() == 0:
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"next": request.query_params.get("next", "/")}
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/", alias="next"),
    container=Depends(get_container),
):
    throttle = request.app.state.login_throttle
    client_ip = request.client.host if request.client else "-"
    locked = throttle.locked_seconds(client_ip, username)
    if locked:
        return redirect_with_flash(
            "/login", f"too many attempts; try again in {locked} seconds"
        )
    user = container.dao.find_user(username)
    pepper = security.load_pepper()
    if user is None:
        security.dummy_verify(password, pepper)
        throttle.record_failure(client_ip, username)
        return redirect_with_flash("/login", "invalid username or password")
    if not security.verify_password(password, user.password_hash, pepper):
        throttle.record_failure(client_ip, username)
        return redirect_with_flash("/login", "invalid username or password")
    if security.needs_rehash(user.password_hash):
        container.dao.update_user_password(username, security.hash_password(password, pepper))
    throttle.record_success(client_ip, username)
    target = next_url if next_url.startswith("/") else "/"
    response = RedirectResponse(target, status_code=303)
    _set_session(response, user.username)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("el_session")
    return response
