"""Provider factories: wire accessors, DAO, and services into the container."""

import os
from pathlib import Path

from ..accessors import DeepSeekAccessor, HttpAccessor, ImapAccessor, SmtpAccessor
from ..accessors.fetch import DEFAULT_USER_AGENT
from ..agent.invoker import Invoker
from ..components.policy import PolicyGate
from ..constants.providers import SMTP_DEFAULT_PORT
from ..dao import SqliteDao
from ..paths import CACHE_DIR, DEFAULT_DB_PATH
from .config_loader import provide_profile, provide_settings
from .container import Container
from .env import load_env_file


def build_llm(settings) -> DeepSeekAccessor:
    return DeepSeekAccessor(
        default_model=settings.model.chat,
        temperature=settings.model.temperature,
    )


def _smtp_port(settings) -> int:
    try:
        return int(os.environ.get("SMTP_PORT") or settings.smtp.port or SMTP_DEFAULT_PORT)
    except ValueError:
        return SMTP_DEFAULT_PORT


def build_mail(settings) -> SmtpAccessor:
    return SmtpAccessor(
        host=os.environ.get("SMTP_HOST", settings.smtp.host),
        port=_smtp_port(settings),
        user=os.environ.get("SMTP_USER", settings.smtp.user),
        password=os.environ.get("SMTP_PASSWORD", ""),
        from_email=os.environ.get(
            "SMTP_FROM", settings.smtp.from_email or settings.sender.email
        ),
        reply_to=os.environ.get("SMTP_REPLY_TO", settings.sender.reply_to),
    )


def build_inbox() -> ImapAccessor:
    return ImapAccessor(
        host=os.environ.get("IMAP_HOST", ""),
        user=os.environ.get("IMAP_USER", ""),
        password=os.environ.get("IMAP_PASSWORD", ""),
    )


def build_http(settings) -> HttpAccessor:
    return HttpAccessor(
        user_agent=settings.sources.user_agent or DEFAULT_USER_AGENT,
        cache_dir=CACHE_DIR,
    )


def refresh_accessors(container) -> None:
    """Rebuild env-backed accessors and the policy gate after config edits."""
    settings = container.settings
    container.llm = build_llm(settings)
    container.mail = build_mail(settings)
    container.inbox = build_inbox()
    container.policy = PolicyGate(container.dao, settings)


def reload_settings(container) -> None:
    container.settings = provide_settings()
    refresh_accessors(container)


def reload_profile(container) -> None:
    container.profile = provide_profile()


def provide_container(
    settings_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> Container:
    load_env_file()
    settings = provide_settings(settings_path)
    profile = provide_profile(profile_path)

    dao = SqliteDao(db_path or os.environ.get("EL_DB_PATH", DEFAULT_DB_PATH))
    dao.init_schema()

    container = Container(
        settings=settings,
        profile=profile,
        dao=dao,
        mail=build_mail(settings),
        http=build_http(settings),
        llm=build_llm(settings),
        inbox=build_inbox(),
        policy=PolicyGate(dao, settings),
    )
    container.invoker = Invoker(container)
    return container
