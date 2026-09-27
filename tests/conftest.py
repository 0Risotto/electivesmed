"""Shared fixtures for the test suite."""

import json
import os
import shutil
import tempfile
from pathlib import Path

# Point all runtime files at an isolated temp root BEFORE importing the app.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="electivesmed-tests-"))
(_TEST_ROOT / "config").mkdir(parents=True, exist_ok=True)
_REPO_ROOT = Path(__file__).resolve().parents[1]
for _name in ("settings.yaml", "profile.yaml"):
    shutil.copy(_REPO_ROOT / "config" / _name, _TEST_ROOT / "config" / _name)
os.environ.setdefault("EL_SETTINGS_PATH", str(_TEST_ROOT / "config" / "settings.yaml"))
os.environ.setdefault("EL_PROFILE_PATH", str(_TEST_ROOT / "config" / "profile.yaml"))
os.environ.setdefault("EL_ENV_PATH", str(_TEST_ROOT / ".env"))
os.environ.setdefault("EL_PEPPER_PATH", str(_TEST_ROOT / "pepper.key"))
os.environ.setdefault("EL_SESSION_KEY_PATH", str(_TEST_ROOT / "session.key"))
# Fast scrypt params for tests only; production defaults are N=2^17 in security.py.
os.environ.setdefault("EL_SCRYPT_N", "16384")
os.environ.setdefault("EL_SCRYPT_R", "8")
os.environ.setdefault("EL_SCRYPT_P", "1")
os.environ.setdefault("EL_SCRYPT_DKLEN", "64")

import pytest  # noqa: E402

from electivesmed.context import reset_invocation, set_invocation  # noqa: E402
from electivesmed.di.providers import provide_container  # noqa: E402
from electivesmed.models.entities import Contact, Draft, Hospital  # noqa: E402
from electivesmed.models.enums import DraftStatus  # noqa: E402
from electivesmed.models.invocation import InvocationContext  # noqa: E402
from electivesmed.models.values import EmailAddress  # noqa: E402

from . import constants as C  # noqa: E402
from .fakes import FakeFetch, FakeLlm, FakeMail, FakeReply, KeepOpen  # noqa: E402

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
def cv_pdf(samples_dir) -> bytes:
    return (samples_dir / "cv_sample.pdf").read_bytes()


@pytest.fixture(scope="session")
def certificate_png(samples_dir) -> bytes:
    return (samples_dir / "certificate_sample.png").read_bytes()


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
