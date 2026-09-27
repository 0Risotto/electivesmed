"""SMTP implementation of MailAccessor (stdlib only)."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from ..constants.limits import SMTP_MAX_MESSAGE_BYTES
from ..constants.providers import SMTP_TIMEOUT_SECONDS
from ..errors import AttachmentError
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
        total_attachment_bytes = sum(len(item.data) for item in payload.attachments)
        if total_attachment_bytes > SMTP_MAX_MESSAGE_BYTES:
            raise AttachmentError(
                f"attachments exceed the {SMTP_MAX_MESSAGE_BYTES // (1024 * 1024)} MB message limit"
            )
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
        for attachment in payload.attachments:
            maintype, _, subtype = attachment.content_type.partition("/")
            msg.add_attachment(
                attachment.data,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        return msg

    def test_connection(self) -> tuple[bool, str]:
        """Connect + STARTTLS + login without sending anything."""
        if not self.host:
            return False, "SMTP_HOST is not configured"
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                if self.user:
                    server.login(self.user, self.password)
            return True, f"connected to {self.host}:{self.port}"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def send(self, payload: MailPayload, dry_run: bool = True) -> SendReceipt:
        try:
            msg = self.build_message(payload)
        except AttachmentError as exc:
            return SendReceipt(
                message_id=None,
                accepted=False,
                status=SendStatus.FAILED,
                error=str(exc),
                dry_run=dry_run,
            )
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
