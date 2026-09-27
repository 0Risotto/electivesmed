"""Configuration models loaded from config/*.yaml."""

from typing import Literal

from pydantic import BaseModel, Field

from ..constants.limits import (
    DAILY_SEND_CAP,
    LLM_TEMPERATURE,
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENT_TOTAL_BYTES,
    MAX_ATTACHMENTS_PER_EMAIL,
    MAX_SEND_DELAY_SECONDS,
    MIN_SEND_DELAY_SECONDS,
    PER_DOMAIN_CAP,
)
from ..constants.providers import (
    DEEPSEEK_CHAT_MODEL,
    DEEPSEEK_REASONER_MODEL,
    SMTP_DEFAULT_PORT,
)

DEFAULT_TONE = "professional, warm, concise"
DEFAULT_LANGUAGE = "en"


class SenderConfig(BaseModel):
    name: str = "Your Name"
    role: str = "Your Role"
    email: str = ""
    reply_to: str = ""
    organization: str = ""
    postal_address: str = ""


class LimitConfig(BaseModel):
    daily_send_cap: int = DAILY_SEND_CAP
    per_domain_cap: int = PER_DOMAIN_CAP
    min_delay_seconds: int = MIN_SEND_DELAY_SECONDS
    max_delay_seconds: int = MAX_SEND_DELAY_SECONDS


class ModelConfig(BaseModel):
    chat: str = DEEPSEEK_CHAT_MODEL
    reasoner: str = DEEPSEEK_REASONER_MODEL
    temperature: float = LLM_TEMPERATURE


class SendingConfig(BaseModel):
    dry_run_default: bool = True
    include_opt_out: bool = True
    window_enabled: bool = True
    window_days: list[int] = Field(default_factory=lambda: [1, 2, 3])  # Tue, Wed, Thu
    window_start: str = "09:00"
    window_end: str = "17:00"


class SmtpConfig(BaseModel):
    host: str = ""
    port: int = SMTP_DEFAULT_PORT
    user: str = ""
    from_email: str = ""


class SourceEntry(BaseModel):
    name: str
    type: str = "csv"
    parser: str = ""
    url: str = ""
    path: str = ""
    country: str = ""
    query: str = ""
    description: str = ""
    enabled: bool = True


class SourceConfig(BaseModel):
    user_agent: str = ""
    entries: list[SourceEntry] = Field(default_factory=list)
    cms_url: str = ""  # legacy: used only when entries is empty


class ComplianceConfig(BaseModel):
    eu_policy: Literal["block", "warn"] = "block"
    us_policy: Literal["block", "warn"] = "block"
    retention_days: int = 730
    jurisdiction_overrides: dict[str, dict] = Field(default_factory=dict)


class WebConfig(BaseModel):
    require_login: bool = True


class AttachmentConfig(BaseModel):
    defaults: list[str] = Field(default_factory=list)
    max_files: int = MAX_ATTACHMENTS_PER_EMAIL
    max_file_mb: int = MAX_ATTACHMENT_BYTES // (1024 * 1024)
    max_total_mb: int = MAX_ATTACHMENT_TOTAL_BYTES // (1024 * 1024)


class Settings(BaseModel):
    sender: SenderConfig = Field(default_factory=SenderConfig)
    limits: LimitConfig = Field(default_factory=LimitConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    sending: SendingConfig = Field(default_factory=SendingConfig)
    smtp: SmtpConfig = Field(default_factory=SmtpConfig)
    sources: SourceConfig = Field(default_factory=SourceConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    attachments: AttachmentConfig = Field(default_factory=AttachmentConfig)
    web: WebConfig = Field(default_factory=WebConfig)


class Profile(BaseModel):
    name: str = ""
    goal: str = "Introduce myself and find matching opportunities and staff contacts."
    ask: str = "Would you be open to a short 15-minute call next week?"
    tone: str = DEFAULT_TONE
    language: str = DEFAULT_LANGUAGE
    specialties: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    hospital_types: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
