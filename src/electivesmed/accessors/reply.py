"""Optional IMAP accessor for reply/bounce detection."""

import email
import imaplib
from email.message import Message
from typing import Protocol

from ..constants.providers import SMTP_TIMEOUT_SECONDS


class ReplyAccessor(Protocol):
    def fetch_replies(self, limit: int = 50) -> list[dict]: ...
    def close(self) -> None: ...


class ImapAccessor:
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        mailbox: str = "INBOX",
        timeout: int = SMTP_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.mailbox = mailbox
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def fetch_replies(self, limit: int = 50) -> list[dict]:
        if not self.configured:
            return []
        results: list[dict] = []
        try:
            with imaplib.IMAP4_SSL(self.host, timeout=self.timeout) as client:
                client.login(self.user, self.password)
                client.select(self.mailbox)
                _, data = client.search(None, "UNSEEN")
                uids = (data[0].split() if data and data[0] else [])[-limit:]
                for uid in uids:
                    _, msg_data = client.fetch(uid, "(RFC822)")
                    if not msg_data or not isinstance(msg_data[0], tuple):
                        continue
                    message: Message = email.message_from_bytes(msg_data[0][1])
                    results.append(
                        {
                            "uid": uid.decode(),
                            "from": message.get("From", ""),
                            "subject": message.get("Subject", ""),
                            "date": message.get("Date", ""),
                        }
                    )
                    client.store(uid, "+FLAGS", "\\Seen")
        except Exception:
            return results
        return results

    def close(self) -> None:
        return None
