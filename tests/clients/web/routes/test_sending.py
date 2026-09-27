from electivesmed.models.entities import Contact, Draft
from electivesmed.models.enums import DraftStatus

from tests import constants as C


def test_send_page_without_approved(client):
    response = client.get("/send")

    assert response.status_code == 200
    assert "No approved drafts" in response.text


def test_send_page_with_approved(client, approved):
    response = client.get("/send")

    assert C.DRAFT_SUBJECT in response.text


def test_dry_run_without_approved(client):
    response = client.post("/send/dry-run", data={}, follow_redirects=True)

    assert "no approved drafts to preview" in response.text


def test_dry_run_renders_previews(client, approved):
    response = client.post(
        "/send/dry-run",
        data={"draft_ids": [approved["draft_id"]]},
    )

    assert response.status_code == 200
    assert "Dry-run results" in response.text
    assert "dry-run 1" in response.text
    assert "remove you from my list" in response.text


def test_dry_run_with_force_window(client, approved):
    response = client.post(
        "/send/dry-run",
        data={"draft_ids": [approved["draft_id"]], "force_window": "true"},
    )

    assert response.status_code == 200
    assert "dry-run 1" in response.text


def test_real_send_without_approved(client):
    response = client.post("/send/real", data={}, follow_redirects=True)

    assert "no approved drafts to send" in response.text


def test_real_send_wrong_confirmation(client, approved):
    response = client.post(
        "/send/real",
        data={"confirm": "nope"},
        follow_redirects=True,
    )

    assert "confirmation did not match" in response.text
    assert C.OPT_OUT not in response.text


def test_real_send_unknown_draft_ids(client, approved):
    response = client.post(
        "/send/real",
        data={"confirm": "SEND 1", "draft_ids": [9999]},
        follow_redirects=True,
    )

    assert "no approved drafts to send" in response.text


def test_real_send_success(
    client, container, approved, fake_mail, open_window, inline_runner
):
    response = client.post(
        "/send/real",
        data={"confirm": "SEND 1", "draft_ids": [approved["draft_id"]]},
    )

    assert response.status_code == 200
    assert "running" in response.text
    assert fake_mail.calls
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.SENT


def test_real_send_uses_approved_queue(
    client, container, approved, fake_mail, open_window, inline_runner
):
    response = client.post("/send/real", data={"confirm": "SEND 1"})

    assert response.status_code == 200
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.SENT


def test_dry_run_skips_drafts_without_contact_email(client, container, seeded):
    contact_id = container.dao.save_contacts(
        [Contact(hospital_id=seeded["hospital_id"], name="No Email")]
    )[0]
    draft_id = container.dao.save_draft(
        Draft(
            invocation_id=C.INVOCATION_ID,
            contact_id=contact_id,
            subject="No email draft",
            body_text=C.DRAFT_BODY,
        )
    )
    container.dao.set_draft_status(draft_id, DraftStatus.APPROVED)

    response = client.post("/send/dry-run", data={"draft_ids": [draft_id]})

    assert response.status_code == 200
    assert "Rendered emails" in response.text
