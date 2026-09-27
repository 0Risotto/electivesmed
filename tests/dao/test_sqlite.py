import sqlite3

import pytest

from electivesmed.dao import SqliteDao
from electivesmed.errors import StoreError
from electivesmed.models.entities import Campaign, Contact, Draft, Hospital, Send
from electivesmed.models.enums import (
    ContactStatus,
    DraftStatus,
    InvocationStatus,
    SendStatus,
    SourceType,
)
from electivesmed.models.invocation import Invocation
from electivesmed.models.values import EmailAddress

from tests import constants as C

# ------------------------------------------------------------------- schema


def test_init_schema_is_idempotent(dao):
    dao.init_schema()
    row = dao._conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert row["value"] == "3"


def test_init_schema_migrates_v1_database(tmp_path):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1');"
        "CREATE TABLE contacts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, hospital_id INTEGER, name TEXT,"
        "title TEXT, department TEXT, email TEXT, source_url TEXT,"
        "confidence REAL NOT NULL DEFAULT 0, fit_score REAL,"
        "fit_reasons TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'new',"
        "created_at TEXT NOT NULL, UNIQUE (email, hospital_id));"
    )
    conn.commit()
    conn.close()

    migrated = SqliteDao(path)
    migrated.init_schema()
    migrated.init_schema()  # idempotent

    columns = {row["name"] for row in migrated._conn.execute("PRAGMA table_info(contacts)")}
    assert {"country", "timezone", "lawful_basis"} <= columns
    version = migrated._conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert version["value"] == "3"

    migrated._conn.execute(
        "INSERT INTO contacts (email, created_at) VALUES ('a@b.org', '2026-01-01T00:00:00')"
    )
    migrated.close()


# ---------------------------------------------------------------- hospitals


def test_upsert_hospital_returns_same_id_and_updates(dao):
    first = dao.upsert_hospital(
        Hospital(name=C.HOSPITAL_NAME, city=C.HOSPITAL_CITY, state=C.HOSPITAL_STATE)
    )
    second = dao.upsert_hospital(
        Hospital(
            name=C.HOSPITAL_NAME,
            city=C.HOSPITAL_CITY,
            state=C.HOSPITAL_STATE,
            website="http://h.test",
            source_type=SourceType.CSV,
        )
    )

    assert first == second
    stored = dao.get_hospital(first)
    assert stored.website == "http://h.test"


def test_get_hospital_missing(dao):
    assert dao.get_hospital(999) is None


def test_find_hospitals_query_and_limit(dao, hospital_id):
    dao.upsert_hospital(Hospital(name="Other Hospital", city="Austin", state="TX"))

    assert len(dao.find_hospitals()) == 2
    assert [h.name for h in dao.find_hospitals(query="Other")] == ["Other Hospital"]
    assert len(dao.find_hospitals(limit=1)) == 1


# ----------------------------------------------------------------- contacts


def test_save_contacts_upserts_by_email(dao, hospital_id):
    ids = dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name=C.CONTACT_NAME,
                email=EmailAddress(value=C.CONTACT_EMAIL),
                confidence=0.2,
            )
        ]
    )
    updated = dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name="Jane R. Doe",
                email=EmailAddress(value=C.CONTACT_EMAIL),
                confidence=0.8,
            )
        ]
    )

    assert ids == updated
    contact = dao.get_contact(ids[0])
    assert contact.name == "Jane R. Doe"
    assert contact.confidence == 0.8


def test_get_contact_missing(dao):
    assert dao.get_contact(999) is None


def test_find_contacts_filters(dao, contact_id):
    dao.save_contacts([Contact(hospital_id=None, name="No Email Contact")])
    dao.update_contact_fit(contact_id, 0.9, ["fit"], ContactStatus.SCORED)

    assert len(dao.find_contacts()) == 1
    assert len(dao.find_contacts(with_email_only=False)) == 2
    assert [c.id for c in dao.find_contacts(scored_only=True)] == [contact_id]
    assert [c.id for c in dao.find_contacts(status=ContactStatus.NEW)] == []


def test_set_contact_status(dao, contact_id):
    dao.set_contact_status(contact_id, ContactStatus.SKIPPED)

    assert dao.get_contact(contact_id).status is ContactStatus.SKIPPED


# ---------------------------------------------------------------- campaigns


def test_upsert_campaign_create_and_update(dao):
    created = dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal="First"))
    updated = dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal="Second"))

    assert created == updated
    assert dao.get_campaign(C.CAMPAIGN_NAME).goal == "Second"


def test_get_campaign_missing(dao):
    assert dao.get_campaign("nope") is None


# ------------------------------------------------------------------- drafts


def test_draft_crud(dao, draft_id):
    draft = dao.get_draft(draft_id)
    assert draft.subject == C.DRAFT_SUBJECT
    assert draft.status is DraftStatus.PENDING
    assert dao.get_draft(999) is None

    dao.set_draft_status(draft_id, DraftStatus.APPROVED)
    approved = dao.get_draft(draft_id)
    assert approved.status is DraftStatus.APPROVED
    assert approved.approved_at is not None

    dao.update_draft_body(draft_id, "New subject", "New body", "<p>New body</p>")
    edited = dao.get_draft(draft_id)
    assert edited.subject == "New subject"
    assert edited.body_html == "<p>New body</p>"


def test_find_drafts_filters(dao, draft_id):
    assert [d.id for d in dao.find_drafts()] == [draft_id]
    assert [d.id for d in dao.find_drafts(DraftStatus.PENDING)] == [draft_id]
    assert dao.find_drafts(DraftStatus.APPROVED) == []


# -------------------------------------------------------------------- sends


def test_record_send_and_counts(dao, draft_id, contact_id):
    sent = dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            to_email=C.CONTACT_EMAIL,
            status=SendStatus.SENT,
        )
    )
    dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            to_email=C.CONTACT_EMAIL,
            status=SendStatus.DRY_RUN,
        )
    )

    assert sent == 1
    assert dao.sends_today() == 1
    assert dao.sends_today_for_domain("testhospital.org") == 1
    assert dao.sends_today_for_domain("other.org") == 0


# ------------------------------------------------------------- suppressions


def test_suppressions_are_normalized(dao):
    dao.add_suppression(" Person@Example.ORG ", "unsubscribe")

    assert dao.is_suppressed("person@example.org")
    assert dao.is_suppressed("PERSON@EXAMPLE.ORG")
    assert not dao.is_suppressed("someone@else.org")
    assert dao.list_suppressions()[0].reason == "unsubscribe"

    dao.add_suppression("person@example.org", "reported")
    assert len(dao.list_suppressions()) == 1
    assert dao.list_suppressions()[0].reason == "reported"


# ------------------------------------------------------------- invocations


def test_invocation_lifecycle(dao):
    invocation = Invocation(
        id="inv_dao",
        agent_name="scout",
        status=InvocationStatus.RUNNING,
        input_json={"prompt": "find"},
    )
    dao.record_invocation(invocation)

    running = dao.get_invocation("inv_dao")
    assert running.status is InvocationStatus.RUNNING
    assert running.output_json is None

    dao.finish_invocation(
        "inv_dao", InvocationStatus.SUCCEEDED, output={"summary": "done"}
    )
    finished = dao.get_invocation("inv_dao")
    assert finished.status is InvocationStatus.SUCCEEDED
    assert finished.output_json == {"summary": "done"}
    assert finished.finished_at is not None
    assert dao.find_invocations()[0].id == "inv_dao"
    assert dao.get_invocation("missing") is None


# ----------------------------------------------------------------- summary


def test_summary_counts(dao, hospital_id, contact_id, draft_id):
    dao.add_suppression("x@y.org")

    summary = dao.summary()

    assert summary["hospitals"] == 1
    assert summary["contacts"] == 1
    assert summary["contacts_with_email"] == 1
    assert summary["drafts_pending"] == 1
    assert summary["suppressed"] == 1
    assert summary["sent_today"] == 0


class _NoRowCursor:
    def fetchone(self):
        return None


class _NoRowConnection:
    def execute(self, *args, **kwargs):
        return _NoRowCursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_store_error_paths(dao, monkeypatch):
    monkeypatch.setattr(dao, "_conn", _NoRowConnection())

    with pytest.raises(StoreError):
        dao.upsert_hospital(Hospital(name="Broken"))
    with pytest.raises(StoreError):
        dao.upsert_campaign(Campaign(name="broken", goal="g"))
    with pytest.raises(StoreError):
        dao.save_draft(
            Draft(
                invocation_id=C.INVOCATION_ID,
                contact_id=1,
                subject="s",
                body_text="b",
            )
        )
    with pytest.raises(StoreError):
        dao.record_send(Send(invocation_id=C.INVOCATION_ID, status=SendStatus.SENT))


# -------------------------------------------------------- compliance fields


def test_contact_compliance_fields_roundtrip(dao, hospital_id):
    ids = dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name="A",
                email=EmailAddress(value=C.CONTACT_EMAIL),
                country="DE",
                timezone="Europe/Berlin",
                lawful_basis="consent",
            )
        ]
    )

    contact = dao.get_contact(ids[0])
    assert (contact.country, contact.timezone, contact.lawful_basis) == (
        "DE",
        "Europe/Berlin",
        "consent",
    )


def test_save_contacts_upgrades_lawful_basis_only(dao, hospital_id):
    def save(**overrides):
        data = dict(hospital_id=hospital_id, name="A", email=EmailAddress(value=C.CONTACT_EMAIL))
        data.update(overrides)
        dao.save_contacts([Contact(**data)])

    save()
    save(lawful_basis="consent")
    assert dao.find_contacts()[0].lawful_basis == "consent"

    save()
    assert dao.find_contacts()[0].lawful_basis == "consent"


# ------------------------------------------------------------- data rights


def test_erase_contact_deletes_and_suppresses(dao, contact_id, draft_id):
    dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            status=SendStatus.SENT,
        )
    )

    result = dao.erase_contact(C.CONTACT_EMAIL)

    assert result == {
        "email": C.CONTACT_EMAIL,
        "contacts_deleted": 1,
        "drafts_deleted": 1,
        "sends_deleted": 1,
    }
    assert dao.get_contact(contact_id) is None
    assert dao.is_suppressed(C.CONTACT_EMAIL)
    assert dao.list_suppressions()[0].reason == "erasure"


def test_erase_contact_unknown_email(dao):
    result = dao.erase_contact("nobody@example.org")

    assert result["contacts_deleted"] == 0


def test_purge_older_than_removes_old_records(dao, contact_id, draft_id):
    dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            status=SendStatus.SENT,
        )
    )
    for table, column in (("sends", "sent_at"), ("drafts", "created_at"), ("contacts", "created_at")):
        dao._conn.execute(f"UPDATE {table} SET {column} = '2000-01-01T00:00:00+00:00'")
    dao._conn.commit()

    result = dao.purge_older_than(30)

    assert result["contacts_deleted"] == 1
    assert result["drafts_deleted"] == 1
    assert result["sends_deleted"] == 1
    assert dao.summary()["contacts"] == 0


def test_purge_keeps_recent_records(dao, contact_id, draft_id):
    dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            status=SendStatus.SENT,
        )
    )

    result = dao.purge_older_than(3650)

    assert result["contacts_deleted"] == 0
    assert result["drafts_deleted"] == 0
    assert result["sends_deleted"] == 0


def test_export_contact_returns_all_records(dao, contact_id, draft_id, hospital_id):
    dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            contact_id=contact_id,
            status=SendStatus.SENT,
        )
    )

    export = dao.export_contact(C.CONTACT_EMAIL)

    assert export["email"] == C.CONTACT_EMAIL
    assert len(export["contacts"]) == 1
    assert len(export["drafts"]) == 1
    assert len(export["sends"]) == 1
    assert export["hospitals"][0]["id"] == hospital_id


def test_export_contact_unknown_email(dao):
    export = dao.export_contact("nobody@example.org")

    assert export["contacts"] == []
    assert export["drafts"] == []
    assert export["sends"] == []
    assert export["hospitals"] == []


def test_update_contact_compliance(dao, contact_id):
    dao.update_contact_compliance(contact_id, "DE", "Europe/Berlin", "consent")

    contact = dao.get_contact(contact_id)
    assert (contact.country, contact.timezone, contact.lawful_basis) == (
        "DE",
        "Europe/Berlin",
        "consent",
    )


def test_get_campaign_by_id_and_find(dao):
    campaign_id = dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal="g"))

    assert dao.get_campaign_by_id(campaign_id).name == C.CAMPAIGN_NAME
    assert dao.get_campaign_by_id(999) is None
    assert [c.name for c in dao.find_campaigns()] == [C.CAMPAIGN_NAME]


def test_dao_is_usable_from_other_threads(dao, hospital_id):
    import threading

    errors: list = []

    def worker():
        try:
            assert dao.summary()["hospitals"] == 1
            dao.add_suppression("thread@example.org", "test")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []
    assert dao.is_suppressed("thread@example.org")


# --------------------------------------------------------------------- users


def test_user_crud(dao):
    assert dao.count_users() == 0

    user_id = dao.create_user("alice", "hash-one")
    assert dao.count_users() == 1
    user = dao.find_user("alice")
    assert user.id == user_id
    assert user.password_hash == "hash-one"
    assert dao.find_user("nobody") is None

    dao.update_user_password("alice", "hash-two")
    assert dao.find_user("alice").password_hash == "hash-two"


# --------------------------------------------------------------- attachments


def _attachment(cv_pdf):
    import hashlib

    from electivesmed.models.entities import Attachment

    return Attachment(
        filename="cv.pdf",
        content_type="application/pdf",
        size=len(cv_pdf),
        sha256=hashlib.sha256(cv_pdf).hexdigest(),
        data=cv_pdf,
    )


def test_attachment_crud_dedupe_and_joins(dao, draft_id, cv_pdf):
    attachment = _attachment(cv_pdf)
    attachment_id = dao.save_attachment(attachment)

    assert dao.save_attachment(attachment) == attachment_id
    assert dao.get_attachment(attachment_id).filename == "cv.pdf"
    assert dao.get_attachment_data(attachment_id) == cv_pdf
    assert dao.find_attachment_by_sha(attachment.sha256).id == attachment_id
    assert [item.filename for item in dao.list_attachments()] == ["cv.pdf"]
    assert dao.get_attachment(999) is None
    assert dao.get_attachment_data(999) is None

    dao.attach_to_draft(draft_id, attachment_id)
    assert [item.id for item in dao.find_draft_attachments(draft_id)] == [attachment_id]
    assert dao.delete_attachment(attachment_id) is True
    assert dao.find_draft_attachments(draft_id) == []


def test_sent_attachment_snapshot_blocks_delete(dao, draft_id, cv_pdf):
    attachment_id = dao.save_attachment(_attachment(cv_pdf))
    send_id = dao.record_send(
        Send(
            invocation_id=C.INVOCATION_ID,
            draft_id=draft_id,
            status=SendStatus.SENT,
        )
    )

    dao.record_sent_attachments(send_id, [dao.get_attachment(attachment_id)])

    assert dao.find_sent_attachments(send_id)[0]["filename"] == "cv.pdf"
    assert dao.delete_attachment(attachment_id) is False


def test_store_error_paths_for_users_and_attachments(dao, monkeypatch, cv_pdf):
    monkeypatch.setattr(dao, "_conn", _NoRowConnection())

    with pytest.raises(StoreError):
        dao.create_user("broken", "hash")
    with pytest.raises(StoreError):
        dao.save_attachment(_attachment(cv_pdf))
