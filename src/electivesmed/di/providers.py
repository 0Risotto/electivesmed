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

    http = HttpAccessor(
        user_agent=settings.sources.user_agent or DEFAULT_USER_AGENT,
        cache_dir=CACHE_DIR,
    )
    llm = DeepSeekAccessor(
        default_model=settings.model.chat,
        temperature=settings.model.temperature,
    )

    try:
        smtp_port = int(os.environ.get("SMTP_PORT") or settings.smtp.port or SMTP_DEFAULT_PORT)
    except ValueError:
        smtp_port = SMTP_DEFAULT_PORT
    mail = SmtpAccessor(
        host=os.environ.get("SMTP_HOST", settings.smtp.host),
        port=smtp_port,
        user=os.environ.get("SMTP_USER", settings.smtp.user),
        password=os.environ.get("SMTP_PASSWORD", ""),
        from_email=os.environ.get(
            "SMTP_FROM", settings.smtp.from_email or settings.sender.email
        ),
        reply_to=os.environ.get("SMTP_REPLY_TO", settings.sender.reply_to),
    )
    inbox = ImapAccessor(
        host=os.environ.get("IMAP_HOST", ""),
        user=os.environ.get("IMAP_USER", ""),
        password=os.environ.get("IMAP_PASSWORD", ""),
    )

    container = Container(
        settings=settings,
        profile=profile,
        dao=dao,
        mail=mail,
        http=http,
        llm=llm,
        inbox=inbox,
        policy=PolicyGate(dao, settings),
    )
    container.invoker = Invoker(container)
    return container
