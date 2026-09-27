"""Core domain entities."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..compliance import DEFAULT_LAWFUL_BASIS
from ..utils.time import utcnow
from .enums import ContactStatus, DraftStatus, SendStatus, SourceType
from .values import EmailAddress


class Hospital(BaseModel):
    id: int | None = None
    name: str
    city: str | None = None
    state: str | None = None
    country: str = ""
    website: str | None = None
    hospital_type: str | None = None
    ownership: str | None = None
    beds: int | None = None
    source_type: SourceType = SourceType.MANUAL
    source_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Contact(BaseModel):
    id: int | None = None
    hospital_id: int | None = None
    hospital_name: str | None = None
    name: str | None = None
    title: str | None = None
    department: str | None = None
    email: EmailAddress | None = None
    country: str | None = None
    timezone: str | None = None
    lawful_basis: str = DEFAULT_LAWFUL_BASIS
    source_url: str | None = None
    confidence: float = 0.0
    fit_score: float | None = None
    fit_reasons: list[str] = Field(default_factory=list)
    status: ContactStatus = ContactStatus.NEW
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def email_value(self) -> str | None:
        return self.email.value if self.email else None


class Campaign(BaseModel):
    id: int | None = None
    name: str
    goal: str
    tone: str = "professional, warm, concise"
    language: str = "en"
    created_at: datetime = Field(default_factory=utcnow)


class Draft(BaseModel):
    id: int | None = None
    invocation_id: str
    contact_id: int
    campaign_id: int | None = None
    subject: str
    body_text: str
    body_html: str | None = None
    rationale: str | None = None
    confidence: float = 0.0
    provider: str = ""
    status: DraftStatus = DraftStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    approved_at: datetime | None = None


class Send(BaseModel):
    id: int | None = None
    invocation_id: str
    draft_id: int | None = None
    contact_id: int | None = None
    message_id: str | None = None
    to_email: str | None = None
    status: SendStatus
    error: str | None = None
    sent_at: datetime = Field(default_factory=utcnow)


class Suppression(BaseModel):
    email: str
    reason: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class User(BaseModel):
    id: int | None = None
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Attachment(BaseModel):
    id: int | None = None
    filename: str
    content_type: str
    size: int
    sha256: str
    data: bytes | None = None
    created_at: datetime = Field(default_factory=utcnow)


class MailAttachment(BaseModel):
    filename: str
    content_type: str
    data: bytes


class MailPayload(BaseModel):
    to: str
    from_email: str
    reply_to: str | None = None
    subject: str
    body_text: str
    body_html: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    attachments: list[MailAttachment] = Field(default_factory=list)


class SendReceipt(BaseModel):
    message_id: str | None = None
    accepted: bool
    status: SendStatus
    error: str | None = None
    dry_run: bool = False


class Source(BaseModel):
    type: SourceType
    name: str
    uri: str
    description: str = ""
