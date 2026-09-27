"""Draft domain → client DTO mapping."""

from ..models.entities import Contact, Draft
from ..models.views import DraftPreview


def draft_to_preview(draft: Draft, contact: Contact | None) -> DraftPreview:
    return DraftPreview(
        id=draft.id or 0,
        to_name=contact.name if contact else None,
        to_email=contact.email_value if contact else None,
        hospital=contact.hospital_name if contact else None,
        subject=draft.subject,
        body_text=draft.body_text,
        rationale=draft.rationale,
        confidence=draft.confidence,
        status=str(draft.status),
        invocation_id=draft.invocation_id,
    )
