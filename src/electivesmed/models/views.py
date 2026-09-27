"""Client-facing DTOs.

Converters produce these from accessor/domain models; clients render them.
Pure data: no I/O, no mapping logic.
"""

from pydantic import BaseModel


class HospitalView(BaseModel):
    id: int | None
    name: str
    location: str
    type: str | None
    website: str | None
    source: str


class ContactView(BaseModel):
    id: int | None
    hospital: str | None
    name: str | None
    title: str | None
    department: str | None
    email: str | None
    country: str | None
    fit_score: float | None
    fit_percent: int | None
    status: str
    source_url: str | None


class ContactInput(BaseModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    email: str | None = None
    hospital_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    timezone: str | None = None
    lawful_basis: str | None = None
    website: str | None = None
    source_url: str | None = None


class DraftPreview(BaseModel):
    id: int
    to_name: str | None
    to_email: str | None
    hospital: str | None
    subject: str
    body_text: str
    rationale: str | None
    confidence: float
    status: str
    invocation_id: str


class DraftEdit(BaseModel):
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None


class SendView(BaseModel):
    id: int | None
    draft_id: int | None
    to_email: str | None
    status: str
    error: str | None
    sent_at: str
    message_id: str | None
    dry_run: bool = False


class InvocationView(BaseModel):
    id: str
    agent: str
    status: str
    campaign_id: int | None
    started_at: str
    finished_at: str | None
    error: str | None
    output: dict | None


class SummaryView(BaseModel):
    hospitals: int
    contacts: int
    contacts_with_email: int
    contacts_scored: int
    drafts_pending: int
    drafts_approved: int
    sent_today: int
    sent_total: int
    suppressed: int
    daily_cap: int
    remaining_today: int
