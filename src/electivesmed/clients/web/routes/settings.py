"""Settings: editable secrets (.env), YAML config, password, connection tests."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from ....components import config_writer, security
from ....di import providers
from ....di.config_loader import profile_path, settings_path
from ....errors import ConfigWriteError, LlmError, LlmUnavailable, SecurityError
from ....models.config import Profile, Settings
from ....paths import ENV_PATH
from ..deps import get_container
from ..helpers import redirect_with_flash
from ..templating import templates

router = APIRouter(prefix="/settings")


def env_path() -> Path:
    return Path(os.environ.get("EL_ENV_PATH", str(ENV_PATH)))


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, container=Depends(get_container)):
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "settings": container.settings,
            "profile": container.profile,
            "username": getattr(request.state, "username", "local"),
            "documents": container.dao.list_attachments(limit=500),
            "secret_state": {
                "deepseek_api_key": bool(container.llm.api_key),
                "smtp_password": bool(container.mail.password),
                "imap_password": bool(container.mail.password) and bool(container.inbox.password),
            },
            "env_values": {
                "smtp_host": container.mail.host,
                "smtp_port": container.mail.port,
                "smtp_user": container.mail.user,
                "smtp_from": container.mail.from_email,
                "smtp_reply_to": container.mail.reply_to or "",
                "imap_host": container.inbox.host,
                "imap_user": container.inbox.user,
            },
        },
    )


@router.post("/env")
def save_env(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: str = Form(""),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form(""),
    smtp_reply_to: str = Form(""),
    imap_host: str = Form(""),
    imap_user: str = Form(""),
    imap_password: str = Form(""),
    deepseek_api_key: str = Form(""),
    clear_smtp_password: bool = Form(False),
    clear_imap_password: bool = Form(False),
    clear_deepseek_api_key: bool = Form(False),
    container=Depends(get_container),
):
    updates: dict[str, str | None] = {
        "SMTP_HOST": smtp_host.strip(),
        "SMTP_PORT": smtp_port.strip(),
        "SMTP_USER": smtp_user.strip(),
        "SMTP_FROM": smtp_from.strip(),
        "SMTP_REPLY_TO": smtp_reply_to.strip(),
        "IMAP_HOST": imap_host.strip(),
        "IMAP_USER": imap_user.strip(),
    }
    if clear_smtp_password:
        updates["SMTP_PASSWORD"] = None
    elif smtp_password.strip():
        updates["SMTP_PASSWORD"] = smtp_password.strip()
    if clear_imap_password:
        updates["IMAP_PASSWORD"] = None
    elif imap_password.strip():
        updates["IMAP_PASSWORD"] = imap_password.strip()
    if clear_deepseek_api_key:
        updates["DEEPSEEK_API_KEY"] = None
    elif deepseek_api_key.strip():
        updates["DEEPSEEK_API_KEY"] = deepseek_api_key.strip()

    try:
        config_writer.write_env_values(updates, env_path())
    except ConfigWriteError as exc:
        return redirect_with_flash("/settings", str(exc))

    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    providers.refresh_accessors(container)
    return redirect_with_flash("/settings", "environment saved (0600)")


@router.post("/config")
def save_config(
    request: Request,
    sender_name: str = Form(""),
    sender_role: str = Form(""),
    sender_email: str = Form(""),
    sender_reply_to: str = Form(""),
    sender_organization: str = Form(""),
    sender_postal_address: str = Form(""),
    daily_send_cap: int = Form(50),
    per_domain_cap: int = Form(2),
    min_delay_seconds: int = Form(60),
    max_delay_seconds: int = Form(180),
    dry_run_default: bool = Form(False),
    include_opt_out: bool = Form(False),
    window_enabled: bool = Form(False),
    window_days: str = Form("1,2,3"),
    window_start: str = Form("09:00"),
    window_end: str = Form("17:00"),
    eu_policy: str = Form("block"),
    us_policy: str = Form("block"),
    retention_days: int = Form(730),
    attachment_defaults: list[str] = Form(default=[]),
    max_files: int = Form(5),
    max_file_mb: int = Form(10),
    max_total_mb: int = Form(20),
    goal: str = Form(""),
    ask: str = Form(""),
    tone: str = Form(""),
    language: str = Form("en"),
    specialties: str = Form(""),
    target_roles: str = Form(""),
    locations: str = Form(""),
    hospital_types: str = Form(""),
    must_haves: str = Form(""),
    avoid: str = Form(""),
    container=Depends(get_container),
):
    days = [int(part) for part in window_days.replace(" ", "").split(",") if part]
    settings_updates = {
        "sender": {
            "name": sender_name.strip(),
            "role": sender_role.strip(),
            "email": sender_email.strip(),
            "reply_to": sender_reply_to.strip(),
            "organization": sender_organization.strip(),
            "postal_address": sender_postal_address.strip(),
        },
        "limits": {
            "daily_send_cap": daily_send_cap,
            "per_domain_cap": per_domain_cap,
            "min_delay_seconds": min_delay_seconds,
            "max_delay_seconds": max_delay_seconds,
        },
        "sending": {
            "dry_run_default": dry_run_default,
            "include_opt_out": include_opt_out,
            "window_enabled": window_enabled,
            "window_days": days or [1, 2, 3],
            "window_start": window_start.strip(),
            "window_end": window_end.strip(),
        },
        "compliance": {
            "eu_policy": eu_policy,
            "us_policy": us_policy,
            "retention_days": retention_days,
        },
        "attachments": {
            "defaults": attachment_defaults,
            "max_files": max_files,
            "max_file_mb": max_file_mb,
            "max_total_mb": max_total_mb,
        },
    }
    profile_updates = {
        "goal": goal.strip(),
        "ask": ask.strip(),
        "tone": tone.strip(),
        "language": language.strip() or "en",
        "specialties": _lines(specialties),
        "target_roles": _lines(target_roles),
        "locations": _lines(locations),
        "hospital_types": _lines(hospital_types),
        "must_haves": _lines(must_haves),
        "avoid": _lines(avoid),
    }

    try:
        Settings.model_validate(
            {**container.settings.model_dump(), **settings_updates}
        )
        Profile.model_validate({**container.profile.model_dump(), **profile_updates})
    except Exception as exc:  # pydantic ValidationError, surfaced to the user
        return redirect_with_flash("/settings", f"invalid settings: {exc}")

    try:
        config_writer.write_yaml_values(settings_path(), settings_updates)
        config_writer.write_yaml_values(profile_path(), profile_updates)
    except ConfigWriteError as exc:
        return redirect_with_flash("/settings", str(exc))
    providers.reload_settings(container)
    providers.reload_profile(container)
    providers.refresh_accessors(container)
    return redirect_with_flash("/settings", "configuration saved")


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


@router.post("/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm: str = Form(...),
    container=Depends(get_container),
):
    username = getattr(request.state, "username", "")
    user = container.dao.find_user(username)
    if user is None:
        return redirect_with_flash("/settings", "unknown user")
    pepper = security.load_pepper()
    if not security.verify_password(current_password, user.password_hash, pepper):
        return redirect_with_flash("/settings", "current password is incorrect")
    if new_password != confirm:
        return redirect_with_flash("/settings", "new passwords do not match")
    try:
        security.validate_password(new_password, username)
    except SecurityError as exc:
        return redirect_with_flash("/settings", str(exc))
    container.dao.update_user_password(username, security.hash_password(new_password, pepper))
    return redirect_with_flash("/settings", "password updated")


@router.post("/test-smtp")
def test_smtp(request: Request, container=Depends(get_container)):
    ok, message = container.mail.test_connection()
    prefix = "SMTP ok" if ok else "SMTP failed"
    return redirect_with_flash("/settings", f"{prefix}: {message}")


@router.post("/test-llm")
def test_llm(request: Request, container=Depends(get_container)):
    try:
        reply = container.llm.chat_text("Reply with the single word: ok", "ping", max_tokens=8)
    except (LlmUnavailable, LlmError) as exc:
        return redirect_with_flash("/settings", f"DeepSeek failed: {exc}")
    return redirect_with_flash("/settings", f"DeepSeek ok: {reply.strip()[:40]}")
