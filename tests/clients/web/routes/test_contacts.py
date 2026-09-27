from electivesmed.models.entities import Campaign, Contact, Send
from electivesmed.models.enums import SendStatus

from tests import constants as C


def test_contacts_list_empty(client):
    response = client.get("/contacts")

    assert response.status_code == 200
    assert "No contacts" in response.text


def test_contacts_list_search_filter(client, seeded):
    response = client.get("/contacts?q=jane")

    assert C.CONTACT_NAME in response.text

    empty = client.get("/contacts?q=zzz")
    assert "No contacts" in empty.text


def test_contacts_list_status_and_country_filters(client, container, seeded):
    scored = client.get("/contacts?status=scored")
    assert "No contacts" in scored.text

    container.dao.update_contact_compliance(seeded["contact_id"], "DE", None, "consent")
    germany = client.get("/contacts?country=de")
    assert C.CONTACT_NAME in germany.text

    elsewhere = client.get("/contacts?country=US")
    assert "No contacts" in elsewhere.text


def test_import_upload(client, container):
    response = client.post(
        "/contacts/import",
        files={"upload": ("c.csv", b"name,email,hospital_name\nA,a@b.org,H\n", "text/csv")},
        data={"hospital": "", "country": "US"},
        follow_redirects=True,
    )

    assert "imported 1 contacts" in response.text
    assert container.dao.summary()["contacts"] == 1


def test_score_endpoint(client, seeded):
    response = client.post("/contacts/score", data={"limit": "10"}, follow_redirects=True)

    assert "scored 1 contacts" in response.text


def test_scout_starts_job_with_campaign(client, container, inline_runner, monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        container.invoker,
        "invoke",
        lambda agent, prompt, campaign_id=None, invocation_id=None: calls.append(campaign_id),
    )
    container.dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL))

    response = client.post(
        "/contacts/scout",
        data={"instructions": "teach", "campaign": C.CAMPAIGN_NAME},
    )

    assert response.status_code == 200
    assert "running" in response.text
    campaign = container.dao.get_campaign(C.CAMPAIGN_NAME)
    assert calls == [campaign.id]


def test_scout_with_unknown_campaign(client, container, inline_runner, monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        container.invoker,
        "invoke",
        lambda agent, prompt, campaign_id=None, invocation_id=None: calls.append(campaign_id),
    )

    response = client.post("/contacts/scout", data={"instructions": "", "campaign": "nope"})

    assert response.status_code == 200
    assert calls == [None]


def test_contact_detail(client, seeded, container):
    container.dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            contact_id=seeded["contact_id"],
            to_email=C.CONTACT_EMAIL,
            status=SendStatus.SENT,
        )
    )

    response = client.get(f"/contacts/{seeded['contact_id']}")

    assert response.status_code == 200
    assert C.CONTACT_NAME in response.text
    assert C.DRAFT_SUBJECT in response.text
    assert "Nothing sent yet" not in response.text


def test_contact_detail_missing(client):
    assert client.get("/contacts/999").status_code == 404


def test_contact_detail_without_email(client, container, seeded):
    contact_id = container.dao.save_contacts(
        [Contact(hospital_id=seeded["hospital_id"], name="No Email")]
    )[0]

    response = client.get(f"/contacts/{contact_id}")

    assert response.status_code == 200
    assert "Nothing sent yet" in response.text


def test_compliance_update(client, container, seeded):
    response = client.post(
        f"/contacts/{seeded['contact_id']}/compliance",
        data={"country": "de", "timezone": "Europe/Berlin", "lawful_basis": "consent"},
        follow_redirects=True,
    )

    assert "compliance fields updated" in response.text
    contact = container.dao.get_contact(seeded["contact_id"])
    assert (contact.country, contact.timezone, contact.lawful_basis) == (
        "DE",
        "Europe/Berlin",
        "consent",
    )


def test_compliance_update_invalid_basis_falls_back(client, container, seeded):
    client.post(
        f"/contacts/{seeded['contact_id']}/compliance",
        data={"country": "", "timezone": "", "lawful_basis": "bogus"},
        follow_redirects=True,
    )

    assert container.dao.get_contact(seeded["contact_id"]).lawful_basis == "unknown"


def test_compliance_update_missing_contact(client):
    assert client.post("/contacts/999/compliance", data={}).status_code == 404


def test_export_endpoint(client, seeded):
    response = client.get(f"/contacts/{seeded['contact_id']}/export")

    assert response.status_code == 200
    assert response.json()["email"] == C.CONTACT_EMAIL
    assert client.get("/contacts/999/export").status_code == 404


def test_erase_with_wrong_confirmation(client, container, seeded):
    response = client.post(
        f"/contacts/{seeded['contact_id']}/erase",
        data={"confirm": "wrong@example.org"},
        follow_redirects=True,
    )

    assert "erase cancelled" in response.text
    assert container.dao.get_contact(seeded["contact_id"]) is not None


def test_erase_with_matching_confirmation(client, container, seeded):
    response = client.post(
        f"/contacts/{seeded['contact_id']}/erase",
        data={"confirm": C.CONTACT_EMAIL},
        follow_redirects=True,
    )

    assert "erased 1 contact records" in response.text
    assert container.dao.get_contact(seeded["contact_id"]) is None
    assert container.dao.is_suppressed(C.CONTACT_EMAIL)
