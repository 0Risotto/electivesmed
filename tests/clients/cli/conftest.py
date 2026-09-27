"""Fixtures for the CLI client tests."""

import types

import pytest
from typer.testing import CliRunner

import electivesmed.clients.cli.app as app_module
from electivesmed.models.entities import Draft
from electivesmed.models.enums import InvocationStatus
from electivesmed.models.invocation import InvocationResult

from tests import constants as C


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def stub_invoker(monkeypatch):
    """Patches container.invoker.invoke and returns the recorded calls."""

    def factory(container, summary: str = "done") -> list:
        calls: list = []

        def fake_invoke(agent_name, prompt, campaign_id=None):
            calls.append(
                {"agent": str(agent_name), "prompt": prompt, "campaign_id": campaign_id}
            )
            return InvocationResult(
                invocation_id="inv_cli",
                status=InvocationStatus.SUCCEEDED,
                output={"summary": summary},
            )

        monkeypatch.setattr(container.invoker, "invoke", fake_invoke)
        return calls

    return factory


@pytest.fixture
def prompt_stub(monkeypatch):
    """Replaces rich Prompt.ask with scripted answers."""

    def factory(answers: list) -> None:
        iterator = iter(answers)
        monkeypatch.setattr(
            app_module, "Prompt", types.SimpleNamespace(ask=lambda *a, **k: next(iterator))
        )

    return factory


@pytest.fixture
def confirm_stub(monkeypatch):
    """Replaces rich Confirm.ask with a fixed answer."""

    def factory(answer: bool) -> None:
        monkeypatch.setattr(
            app_module, "Confirm", types.SimpleNamespace(ask=lambda *a, **k: answer)
        )

    return factory


@pytest.fixture
def second_draft(container):
    """Creates an additional pending draft for a contact."""

    def factory(contact_id: int) -> int:
        return container.dao.save_draft(
            Draft(
                invocation_id=C.INVOCATION_ID,
                contact_id=contact_id,
                subject="Second subject",
                body_text=C.DRAFT_BODY,
            )
        )

    return factory
