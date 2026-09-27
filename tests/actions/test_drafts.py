import pytest

from electivesmed.actions.drafts import save_draft
from electivesmed.models.entities import Campaign
from electivesmed.models.enums import DraftStatus

from tests import constants as C


def test_save_draft_creates_pending_draft(container, seeded, invocation_ctx):
    result = save_draft(
        container,
        seeded["contact_id"],
        C.CAMPAIGN_NAME,
        "A short subject",
        C.CLEAN_BODY,
        rationale="Matched role and location",
        confidence=1.5,
    )

    assert result["status"] == "pending_review"
    assert result["invocation_id"] == C.INVOCATION_ID

    draft = container.dao.get_draft(result["draft_id"])
    assert draft.status is DraftStatus.PENDING
    assert draft.campaign_id is None
    assert draft.confidence == 1.0
    assert draft.provider == container.settings.model.chat


def test_save_draft_links_existing_campaign(container, seeded, invocation_ctx):
    campaign_id = container.dao.upsert_campaign(
        Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    )

    result = save_draft(container, seeded["contact_id"], C.CAMPAIGN_NAME, "Subject", C.CLEAN_BODY)
    draft = container.dao.get_draft(result["draft_id"])

    assert draft.campaign_id == campaign_id


def test_save_draft_denied_for_unknown_contact(container, invocation_ctx):
    result = save_draft(container, 999, C.CAMPAIGN_NAME, "Subject", C.CLEAN_BODY)

    assert result["status"] == "denied"
    assert "unknown contact" in result["reason"]


def test_save_draft_denied_for_suppressed_contact(container, seeded, invocation_ctx):
    container.dao.add_suppression(C.CONTACT_EMAIL, "unsubscribe")

    result = save_draft(container, seeded["contact_id"], C.CAMPAIGN_NAME, "Subject", C.CLEAN_BODY)

    assert result["status"] == "denied"
    assert "suppressed" in result["reason"]


def test_save_draft_requires_invocation_context(container, seeded):
    with pytest.raises(RuntimeError, match="invocation"):
        save_draft(container, seeded["contact_id"], C.CAMPAIGN_NAME, "Subject", C.CLEAN_BODY)
