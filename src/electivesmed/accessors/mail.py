"""SMTP implementation of MailAccessor (stdlib only)."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from ..constants.providers import SMTP_TIMEOUT_SECONDS
from ..models.entities import MailPayload, SendReceipt
from ..models.enums import SendStatus


class MailAccessor(Protocol):
    def send(self, payload: MailPayload, dry_run: bool = True) -> SendReceipt: ...
    def close(self) -> None: ...


class SmtpAccessor:
    def __init__(
        self,
        host: str,
        port: int,
        user: str = "",
        password: str = "",
        from_email: str = "",
        reply_to: str = "",
        timeout: int = SMTP_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.reply_to = reply_to or None
        self.timeout = timeout

    def build_message(self, payload: MailPayload) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = payload.from_email or self.from_email
        msg["To"] = payload.to
        if payload.reply_to or self.reply_to:
            msg["Reply-To"] = payload.reply_to or self.reply_to
        msg["Subject"] = payload.subject
        msg["Message-ID"] = make_msgid()
        for key, value in payload.headers.items():
            msg[key] = value
        msg.set_content(payload.body_text)
        if payload.body_html:
            msg.add_alternative(payload.body_html, subtype="html")
        return msg

    def send(self, payload: MailPayload, dry_run: bool = True) -> SendReceipt:
        msg = self.build_message(payload)
        message_id = msg["Message-ID"]

        if dry_run:
            return SendReceipt(
                message_id=message_id,
                accepted=True,
                status=SendStatus.DRY_RUN,
                dry_run=True,
            )

        if not self.host:
            return SendReceipt(
                message_id=message_id,
                accepted=False,
                status=SendStatus.FAILED,
                error="SMTP_HOST is not configured",
            )

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return SendReceipt(message_id=message_id, accepted=True, status=SendStatus.SENT)
        except Exception as exc:  # network/auth errors are expected at runtime
            return SendReceipt(
                message_id=message_id,
                accepted=False,
                status=SendStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )

    def close(self) -> None:
        return None
