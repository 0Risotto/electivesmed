from electivesmed.converters.draft import draft_to_preview
from electivesmed.models.entities import Draft

from tests import constants as C


def test_draft_to_preview_with_contact(container, seeded):
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])

    preview = draft_to_preview(draft, contact)

    assert preview.id == seeded["draft_id"]
    assert preview.to_email == C.CONTACT_EMAIL
    assert preview.hospital == C.HOSPITAL_NAME
    assert preview.status == "pending"
    assert preview.invocation_id == C.INVOCATION_ID


def test_draft_to_preview_without_contact():
    draft = Draft(
        id=9,
        invocation_id=C.INVOCATION_ID,
        contact_id=1,
        subject=C.DRAFT_SUBJECT,
        body_text=C.DRAFT_BODY,
    )

    preview = draft_to_preview(draft, None)

    assert preview.to_name is None
    assert preview.to_email is None
    assert preview.hospital is None
