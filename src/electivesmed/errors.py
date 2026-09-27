"""Typed errors shared across layers."""


class OutreachError(Exception):
    """Base error for the application."""


class ConfigError(OutreachError):
    """Invalid or missing configuration."""


class LlmUnavailable(OutreachError):
    """No API key or provider configured for LLM calls."""


class LlmError(OutreachError):
    """LLM call failed or returned malformed output."""


class FetchError(OutreachError):
    """Remote fetch failed."""


class StoreError(OutreachError):
    """Persistence failure."""


class SecurityError(OutreachError):
    """Credential, session, or hashing failure."""


class AttachmentError(OutreachError):
    """Attachment validation or storage failure."""


class ConfigWriteError(OutreachError):
    """Failed to persist configuration."""


class PolicyDenied(OutreachError):
    """An action was blocked by the policy gate."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
