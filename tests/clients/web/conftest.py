"""Fixtures for the web client tests."""

import os

import pytest
from fastapi.testclient import TestClient

from electivesmed.clients.web.app import create_app
from electivesmed.components import security
from electivesmed.models.entities import Campaign, Draft

from tests import constants as C

TEST_USER = "tester"
TEST_PASSWORD = "correct-horse-battery"

_ENV_KEYS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_REPLY_TO",
    "IMAP_HOST",
    "IMAP_USER",
    "IMAP_PASSWORD",
    "DEEPSEEK_API_KEY",
)


@pytest.fixture(autouse=True)
def _restore_config_state():
    """The settings UI writes os.environ and the config files; restore both."""
    from electivesmed.clients.web.routes.settings import env_path
    from electivesmed.di.config_loader import profile_path, settings_path

    before_env = {key: os.environ.get(key) for key in _ENV_KEYS}
    files = [settings_path(), profile_path(), env_path()]
    snapshots = {path: (path.read_bytes() if path.exists() else None) for path in files}
    yield
    for path, data in snapshots.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(data)
    for key, value in before_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class InlineRunner:
    """Runs submitted jobs synchronously for deterministic tests."""

    def __init__(self) -> None:
        self.submitted = 0

    def submit(self, fn, *args, **kwargs) -> None:
        self.submitted += 1
        fn(*args, **kwargs)

    def shutdown(self) -> None:
        pass


@pytest.fixture
def client(container):
    if container.dao.count_users() == 0:
        container.dao.create_user(TEST_USER, security.hash_password(TEST_PASSWORD))
    app = create_app(container=container)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/login", data={"username": TEST_USER, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200  # followed the redirect to "/"
        yield test_client


@pytest.fixture
def inline_runner(client, monkeypatch):
    runner = InlineRunner()
    monkeypatch.setattr(client.app.state, "runner", runner)
    return runner


@pytest.fixture
def campaign_draft(container, seeded):
    campaign_id = container.dao.upsert_campaign(
        Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    )
    draft_id = container.dao.save_draft(
        Draft(
            invocation_id=C.INVOCATION_ID,
            contact_id=seeded["contact_id"],
            campaign_id=campaign_id,
            subject="Campaign draft",
            body_text=C.DRAFT_BODY,
        )
    )
    return {"campaign_id": campaign_id, "draft_id": draft_id}
