from electivesmed.models.entities import Contact, Draft
from electivesmed.models.enums import DraftStatus

from tests import constants as C


def _second_draft(container, contact_id: int, subject: str = "Second subject") -> int:
    return container.dao.save_draft(
        Draft(
            invocation_id=C.INVOCATION_ID,
            contact_id=contact_id,
            subject=subject,
            body_text=C.DRAFT_BODY,
        )
    )


def test_inbox_lists_pending(client, seeded):
    response = client.get("/drafts")

    assert response.status_code == 200
    assert C.DRAFT_SUBJECT in response.text


def test_inbox_filters_by_status_and_falls_back(client, seeded):
    approved_page = client.get("/drafts?status=approved")
    assert "No drafts with this status" in approved_page.text

    fallback = client.get("/drafts?status=bogus")
    assert C.DRAFT_SUBJECT in fallback.text


def test_editor_renders_personalization(client, seeded):
    response = client.get(f"/drafts/{seeded['draft_id']}")

    assert response.status_code == 200
    assert "Personalization" in response.text
    assert C.CONTACT_NAME in response.text
    assert "style ok" in response.text
    assert "remove you from my list" in response.text


def test_editor_missing(client):
    assert client.get("/drafts/999").status_code == 404


def test_editor_with_campaign(client, campaign_draft):
    response = client.get(f"/drafts/{campaign_draft['draft_id']}")

    assert C.CAMPAIGN_NAME in response.text


def test_editor_without_contact(client, container, seeded, monkeypatch):
    monkeypatch.setattr(container.dao, "get_contact", lambda contact_id: None)

    assert client.get(f"/drafts/{seeded['draft_id']}").status_code == 404


def test_editor_without_email_contact(client, container, seeded):
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

    response = client.get(f"/drafts/{draft_id}")

    assert response.status_code == 200
    assert "no email address for this contact" in response.text


def test_save_updates_draft(client, container, seeded):
    response = client.post(
        f"/drafts/{seeded['draft_id']}/save",
        data={"subject": "New subject", "body": C.CLEAN_BODY},
        follow_redirects=True,
    )

    assert "draft saved" in response.text
    draft = container.dao.get_draft(seeded["draft_id"])
    assert draft.subject == "New subject"
    assert draft.body_text == C.CLEAN_BODY


def test_save_rejects_empty_fields(client, container, seeded):
    response = client.post(
        f"/drafts/{seeded['draft_id']}/save",
        data={"subject": " ", "body": ""},
        follow_redirects=True,
    )

    assert "subject and body are required" in response.text
    assert container.dao.get_draft(seeded["draft_id"]).subject == C.DRAFT_SUBJECT


def test_lint_reports_violations(client, seeded):
    response = client.post(
        f"/drafts/{seeded['draft_id']}/lint",
        data={"subject": "Hello", "body": "Hi \u2014 we can leverage this."},
    )

    assert "em dash" in response.text
    assert "AI-typical words" in response.text


def test_lint_clean_copy(client, seeded):
    response = client.post(
        f"/drafts/{seeded['draft_id']}/lint",
        data={"subject": "Hello", "body": C.CLEAN_BODY},
    )

    assert "style ok" in response.text


def test_approve_and_reject(client, container, seeded):
    second = _second_draft(container, seeded["contact_id"], subject="To reject")

    client.post(f"/drafts/{seeded['draft_id']}/approve", follow_redirects=True)
    client.post(f"/drafts/{second}/reject", follow_redirects=True)

    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.APPROVED
    assert container.dao.get_draft(second).status is DraftStatus.REJECTED


def test_suppress_rejects_and_suppresses(client, container, seeded):
    response = client.post(f"/drafts/{seeded['draft_id']}/suppress", follow_redirects=True)

    assert "suppressed and rejected" in response.text
    assert container.dao.is_suppressed(C.CONTACT_EMAIL)
    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.REJECTED


def test_suppress_without_contact_still_rejects(client, container, seeded, monkeypatch):
    monkeypatch.setattr(container.dao, "get_contact", lambda contact_id: None)

    client.post(f"/drafts/{seeded['draft_id']}/suppress", follow_redirects=True)

    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.REJECTED


def test_regenerate_starts_job(client, container, seeded, inline_runner, monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        container.invoker,
        "invoke",
        lambda agent, prompt, campaign_id=None, invocation_id=None: calls.append(invocation_id),
    )

    response = client.post(
        f"/drafts/{seeded['draft_id']}/regenerate", data={"instructions": "shorter"}
    )

    assert response.status_code == 200
    assert "running" in response.text
    assert calls and calls[0]


def test_regenerate_missing_contact(client, container, seeded, monkeypatch):
    monkeypatch.setattr(container.dao, "get_contact", lambda contact_id: None)

    response = client.post(f"/drafts/{seeded['draft_id']}/regenerate", data={})

    assert response.status_code == 404


def test_bulk_approve(client, container, seeded):
    second = _second_draft(container, seeded["contact_id"])

    client.post(
        "/drafts/bulk",
        data={"action": "approve", "draft_ids": [seeded["draft_id"], second]},
        follow_redirects=True,
    )

    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.APPROVED
    assert container.dao.get_draft(second).status is DraftStatus.APPROVED


def test_bulk_reject_and_suppress(client, container, seeded):
    second = _second_draft(container, seeded["contact_id"])

    client.post(
        "/drafts/bulk",
        data={"action": "reject", "draft_ids": [seeded["draft_id"]]},
        follow_redirects=True,
    )
    response = client.post(
        "/drafts/bulk",
        data={"action": "suppress", "draft_ids": [second]},
        follow_redirects=True,
    )

    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.REJECTED
    assert container.dao.is_suppressed(C.CONTACT_EMAIL)
    assert "suppressed 1 drafts" in response.text


def test_bulk_unknown_action(client, container, seeded):
    response = client.post(
        "/drafts/bulk",
        data={"action": "explode", "draft_ids": [seeded["draft_id"]]},
        follow_redirects=True,
    )

    assert "unknown action" in response.text
    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.PENDING


def test_bulk_skips_missing_ids(client, container, seeded):
    client.post(
        "/drafts/bulk",
        data={"action": "approve", "draft_ids": [9999]},
        follow_redirects=True,
    )

    assert container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.PENDING


# --------------------------------------------------------------- attachments


def test_attach_and_detach_documents(client, container, seeded, cv_pdf):
    from electivesmed.services.attachments import add_attachment

    attachment = add_attachment(container, "cv.pdf", cv_pdf)

    attached = client.post(
        f"/drafts/{seeded['draft_id']}/attach",
        data={"attachment_ids": [attachment.id]},
        follow_redirects=True,
    )
    assert "attached 1 document(s)" in attached.text
    assert "cv.pdf" in client.get(f"/drafts/{seeded['draft_id']}").text

    detached = client.post(
        f"/drafts/{seeded['draft_id']}/detach",
        data={"attachment_id": attachment.id},
        follow_redirects=True,
    )
    assert "attachment removed" in detached.text
    assert container.dao.find_draft_attachments(seeded["draft_id"]) == []


def test_attach_without_selection(client, seeded):
    response = client.post(
        f"/drafts/{seeded['draft_id']}/attach", data={}, follow_redirects=True
    )

    assert "no documents selected" in response.text


def test_attach_limit_error(client, container, seeded, cv_pdf):
    from electivesmed.services.attachments import add_attachment

    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    container.settings.attachments.max_files = 0

    response = client.post(
        f"/drafts/{seeded['draft_id']}/attach",
        data={"attachment_ids": [attachment.id]},
        follow_redirects=True,
    )

    assert "attach failed" in response.text
