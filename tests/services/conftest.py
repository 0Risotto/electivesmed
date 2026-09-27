"""Fixtures for the service (activity) layer."""

import pytest

from electivesmed.models.entities import Draft
from electivesmed.models.enums import DraftStatus

from tests import constants as C


@pytest.fixture
def approved_draft_factory(container):
    """Creates and approves a draft for a contact; returns the draft id."""

    def factory(contact_id: int, subject: str = "Follow up") -> int:
        draft_id = container.dao.save_draft(
            Draft(
                invocation_id=C.INVOCATION_ID,
                contact_id=contact_id,
                subject=subject,
                body_text=C.DRAFT_BODY,
            )
        )
        container.dao.set_draft_status(draft_id, DraftStatus.APPROVED)
        return draft_id

    return factory
