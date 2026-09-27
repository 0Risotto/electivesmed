"""Accessor layer: external service calls (SMTP, HTTP, DeepSeek, IMAP).

Each module pairs one capability protocol with its default implementation.
"""

from .fetch import FetchAccessor, HttpAccessor
from .llm import DeepSeekAccessor, LlmAccessor
from .mail import MailAccessor, SmtpAccessor
from .reply import ImapAccessor, ReplyAccessor

__all__ = [
    "MailAccessor",
    "SmtpAccessor",
    "FetchAccessor",
    "HttpAccessor",
    "LlmAccessor",
    "DeepSeekAccessor",
    "ReplyAccessor",
    "ImapAccessor",
]
