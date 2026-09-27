"""Shared fixtures for the test suite."""

import json
from pathlib import Path

import pytest

from electivesmed.context import reset_invocation, set_invocation
from electivesmed.di.providers import provide_container
from electivesmed.models.entities import Contact, Draft, Hospital
from electivesmed.models.enums import DraftStatus
from electivesmed.models.invocation import InvocationContext
from electivesmed.models.values import EmailAddress

from . import constants as C
from .fakes import FakeFetch, FakeLlm, FakeMail, FakeReply, KeepOpen

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"


# ------------------------------------------------------------ sample datasets


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return SAMPLES_DIR


@pytest.fixture(scope="session")
def cms_csv(samples_dir) -> bytes:
    return (samples_dir / "hospitals_cms.csv").read_bytes()


@pytest.fixture(scope="session")
def extraction_response(samples_dir) -> dict:
    return json.loads((samples_dir / "extraction_response.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def staff_page_html(samples_dir) -> bytes:
    return (samples_dir / "staff_page.html").read_bytes()


@pytest.fixture(scope="session")
def contacts_csv(samples_dir) -> Path:
    return samples_dir / "contacts.csv"


@pytest.fixture(scope="session")
def generic_hospitals_csv(samples_dir) -> Path:
    return samples_dir / "generic_hospitals.csv"


@pytest.fixture(scope="session")
def osm_response(samples_dir) -> dict:
    return json.loads((samples_dir / "osm_response.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def wikidata_response(samples_dir) -> dict:
    return json.loads((samples_dir / "wikidata_response.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ container


@pytest.fixture
def container(tmp_path):
    instance = provide_container(db_path=tmp_path / "test.db")
    yield instance
    instance.close()


@pytest.fixture
def seeded(container):
    """Hospital + contact + pending draft."""
    hospital_id = container.dao.upsert_hospital(
        Hospital(name=C.HOSPITAL_NAME, city=C.HOSPITAL_CITY, state=C.HOSPITAL_STATE)
    )
    contact_ids = container.dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name=C.CONTACT_NAME,
                title=C.CONTACT_TITLE,
                email=EmailAddress(value=C.CONTACT_EMAIL),
            )
        ]
    )
    contact_id = contact_ids[0]
    draft_id = container.dao.save_draft(
        Draft(
            invocation_id=C.INVOCATION_ID,
            contact_id=contact_id,
            subject=C.DRAFT_SUBJECT,
            body_text=C.DRAFT_BODY,
        )
    )
    return {
        "hospital_id": hospital_id,
        "contact_id": contact_id,
        "draft_id": draft_id,
    }


@pytest.fixture
def approved(container, seeded):
    """Seeded draft with status APPROVED."""
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    return seeded


@pytest.fixture
def invocation_ctx():
    ctx = InvocationContext(invocation_id=C.INVOCATION_ID, agent_name="test")
    token = set_invocation(ctx)
    yield ctx
    reset_invocation(token)


@pytest.fixture
def fake_mail(container):
    mail = FakeMail()
    container.mail = mail
    return mail


@pytest.fixture
def fake_llm(container):
    llm = FakeLlm()
    container.llm = llm
    return llm


@pytest.fixture
def fake_fetch(container, cms_csv):
    fetch = FakeFetch(data=cms_csv)
    container.http = fetch
    return fetch


@pytest.fixture
def fake_reply(container):
    reply = FakeReply()
    container.inbox = reply
    return reply


@pytest.fixture
def open_window(container):
    """Disables the recipient-local send window for deterministic real sends."""
    container.settings.sending.window_enabled = False
    return container.settings.sending


@pytest.fixture
def cli_container(container, monkeypatch):
    """Point CLI commands at the shared test container without closing it."""
    import electivesmed.clients.cli.app as app_module

    monkeypatch.setattr(app_module, "provide_container", lambda **kwargs: KeepOpen(container))
    return container
