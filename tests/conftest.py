import pytest

from hospital_outreach.di.providers import provide_container
from hospital_outreach.models.entities import Contact, Draft, Hospital
from hospital_outreach.models.values import EmailAddress


@pytest.fixture
def container(tmp_path):
    c = provide_container(db_path=tmp_path / "test.db")
    yield c
    c.close()


@pytest.fixture
def seeded(container):
    """Hospital + contact + pending draft, ready for policy/send tests."""
    hospital_id = container.dao.upsert_hospital(
        Hospital(name="Test Hospital", city="Fresno", state="CA")
    )
    contact_ids = container.dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name="Jane Doe",
                title="Chief Medical Officer",
                email=EmailAddress(value="jane.doe@testhospital.org"),
            )
        ]
    )
    contact_id = contact_ids[0]
    draft = Draft(
        invocation_id="inv_test",
        contact_id=contact_id,
        subject="Hello from a colleague",
        body_text="Hi Jane, this is a short professional note.",
    )
    draft_id = container.dao.save_draft(draft)
    return {"hospital_id": hospital_id, "contact_id": contact_id, "draft_id": draft_id}


@pytest.fixture
def invocation_ctx():
    from hospital_outreach.context import reset_invocation, set_invocation
    from hospital_outreach.models.invocation import InvocationContext

    ctx = InvocationContext(invocation_id="inv_test", agent_name="test")
    token = set_invocation(ctx)
    yield ctx
    reset_invocation(token)
