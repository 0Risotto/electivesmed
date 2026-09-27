from electivesmed.clients.web.jobs import (
    run_generate,
    run_regenerate,
    run_scout,
    run_send,
)
from electivesmed.models.entities import Campaign, Contact
from electivesmed.models.enums import AgentName, InvocationStatus

from tests import constants as C


def _stub_invoke(container, monkeypatch) -> list:
    calls: list = []

    def fake_invoke(agent_name, prompt, campaign_id=None, invocation_id=None):
        calls.append(
            {
                "agent": agent_name,
                "prompt": prompt,
                "campaign_id": campaign_id,
                "invocation_id": invocation_id,
            }
        )

    monkeypatch.setattr(container.invoker, "invoke", fake_invoke)
    return calls


def test_run_scout_forwards_instructions_and_campaign(container, monkeypatch):
    calls = _stub_invoke(container, monkeypatch)

    run_scout(container, "inv_scout", "teaching hospitals", 7)

    assert calls[0]["agent"] == AgentName.SCOUT
    assert calls[0]["campaign_id"] == 7
    assert calls[0]["invocation_id"] == "inv_scout"
    assert "teaching hospitals" in calls[0]["prompt"]


def test_run_generate_uses_campaign(container, monkeypatch):
    calls = _stub_invoke(container, monkeypatch)
    campaign = Campaign(id=3, name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    contacts = [Contact(name=C.CONTACT_NAME)]
    contacts[0].id = 1

    run_generate(container, "inv_gen", campaign, contacts, "be brief")

    assert calls[0]["agent"] == AgentName.OUTREACH
    assert calls[0]["campaign_id"] == 3
    assert "be brief" in calls[0]["prompt"]


def test_run_regenerate_without_campaign_uses_profile(container, monkeypatch):
    calls = _stub_invoke(container, monkeypatch)
    contact = Contact(name=C.CONTACT_NAME)
    contact.id = 5

    run_regenerate(container, "inv_regen", contact)

    assert calls[0]["campaign_id"] is None
    assert container.profile.goal in calls[0]["prompt"]


def test_run_regenerate_with_campaign(container, monkeypatch):
    calls = _stub_invoke(container, monkeypatch)
    campaign = Campaign(id=2, name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    contact = Contact(name=C.CONTACT_NAME)
    contact.id = 6

    run_regenerate(container, "inv_regen2", contact, campaign)

    assert calls[0]["campaign_id"] == 2


def test_run_send_records_invocation_output(container, approved, fake_mail, open_window):
    run_send(container, "inv_send", [approved["draft_id"]], force_window=True)

    invocation = container.dao.get_invocation("inv_send")
    assert invocation.status is InvocationStatus.SUCCEEDED
    assert invocation.output_json["attempted"] == 1
    assert fake_mail.calls
