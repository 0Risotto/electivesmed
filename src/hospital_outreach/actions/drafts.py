"""Action: persist an AI-drafted outreach email for human review."""

from ..context import require_invocation
from ..converters.contact import contact_to_view
from ..models.entities import Draft
from ..models.enums import DraftStatus


def save_draft(
    container,
    contact_id: int,
    campaign_name: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    rationale: str = "",
    confidence: float = 0.0,
) -> dict:
    ctx = require_invocation()
    contact = container.dao.get_contact(contact_id)
    decision = container.policy.check_save_draft(contact, subject, body_text)
    if not decision.allowed:
        return {"status": "denied", "reason": decision.reason}

    campaign = container.dao.get_campaign(campaign_name)
    draft = Draft(
        invocation_id=ctx.invocation_id,
        contact_id=contact_id,
        campaign_id=campaign.id if campaign else None,
        subject=subject.strip()[:120],
        body_text=body_text.strip(),
        body_html=body_html.strip() or None,
        rationale=rationale.strip() or None,
        confidence=max(0.0, min(1.0, float(confidence))),
        provider=container.settings.model.chat,
        status=DraftStatus.PENDING,
    )
    draft_id = container.dao.save_draft(draft)
    return {
        "status": "pending_review",
        "draft_id": draft_id,
        "invocation_id": ctx.invocation_id,
        "contact": contact_to_view(contact).model_dump(mode="json"),
        "warnings": list(decision.warnings),
    }
