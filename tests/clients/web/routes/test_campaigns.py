from electivesmed.models.entities import Campaign
from electivesmed.models.enums import ContactStatus

from tests import constants as C


def test_campaigns_empty(client):
    response = client.get("/campaigns")

    assert response.status_code == 200
    assert "No campaigns yet" in response.text


def test_create_campaign(client, container):
    response = client.post(
        "/campaigns",
        data={"name": C.CAMPAIGN_NAME, "goal": "", "tone": "", "language": "en"},
        follow_redirects=True,
    )

    assert "saved" in response.text
    campaign = container.dao.get_campaign(C.CAMPAIGN_NAME)
    assert campaign is not None
    assert campaign.goal == container.profile.goal


def test_create_campaign_requires_name(client):
    response = client.post(
        "/campaigns", data={"name": "  "}, follow_redirects=True
    )

    assert "campaign name is required" in response.text


def test_generate_missing_campaign(client):
    assert client.post("/campaigns/999/generate", data={}).status_code == 404


def test_generate_without_contacts(client, container):
    campaign_id = container.dao.upsert_campaign(
        Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    )

    response = client.post(
        f"/campaigns/{campaign_id}/generate", data={"limit": "5", "min_score": "0.3"},
        follow_redirects=True,
    )

    assert "no contacts available" in response.text


def test_generate_selects_scored_contacts(
    client, container, seeded, inline_runner, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        container.invoker,
        "invoke",
        lambda agent, prompt, campaign_id=None, invocation_id=None: calls.append(prompt),
    )
    campaign_id = container.dao.upsert_campaign(
        Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    )
    container.dao.update_contact_fit(
        seeded["contact_id"], 0.9, ["great fit"], ContactStatus.SCORED
    )

    response = client.post(
        f"/campaigns/{campaign_id}/generate",
        data={"limit": "5", "min_score": "0.5", "instructions": "be specific"},
    )

    assert response.status_code == 200
    assert "running" in response.text
    assert calls and str(seeded["contact_id"]) in calls[0]
    assert "be specific" in calls[0]


def test_generate_falls_back_to_contacts_with_email(
    client, container, seeded, inline_runner, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        container.invoker,
        "invoke",
        lambda agent, prompt, campaign_id=None, invocation_id=None: calls.append(prompt),
    )
    campaign_id = container.dao.upsert_campaign(
        Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL)
    )

    response = client.post(
        f"/campaigns/{campaign_id}/generate",
        data={"limit": "5", "min_score": "0.9"},
    )

    assert response.status_code == 200
    assert calls and str(seeded["contact_id"]) in calls[0]
