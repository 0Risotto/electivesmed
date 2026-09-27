"""SQLite implementation of the Dao protocol."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from ..errors import StoreError
from ..models.entities import (
    Attachment,
    Campaign,
    Contact,
    Draft,
    Hospital,
    Send,
    Suppression,
    User,
)
from ..models.enums import ContactStatus, DraftStatus, InvocationStatus, SendStatus
from ..models.invocation import Invocation
from ..utils.time import utcnow
from . import mappers
from .schema import MIGRATIONS, SCHEMA, SCHEMA_VERSION


class SqliteDao:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the web UI and background runner share this DAO.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._write_lock = threading.RLock()

    @contextmanager
    def _tx(self):
        """Serialize write transactions across threads sharing this connection."""
        with self._write_lock:
            with self._conn:
                yield

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        with self._tx():
            self._conn.executescript(SCHEMA)
            stored = self._stored_version()
            if stored is None:
                self._write_version(SCHEMA_VERSION)
                return
            for target in range(stored + 1, SCHEMA_VERSION + 1):
                for statement in MIGRATIONS.get(target, []):
                    self._conn.execute(statement)
                self._write_version(target)

    def _stored_version(self) -> int | None:
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"]) if row else None

    def _write_version(self, version: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )

    def close(self) -> None:
        self._conn.close()

    # --------------------------------------------------------------- hospitals
    def upsert_hospital(self, hospital: Hospital) -> int:
        fields = (
            hospital.name,
            hospital.city,
            hospital.state,
            hospital.country,
            hospital.website,
            hospital.hospital_type,
            hospital.ownership,
            hospital.beds,
            str(hospital.source_type),
            hospital.source_url,
            mappers.dt(hospital.created_at),
        )
        with self._tx():
            row = self._conn.execute(
                """
                INSERT INTO hospitals
                    (name, city, state, country, website, hospital_type, ownership,
                     beds, source_type, source_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (name, city, state) DO UPDATE SET
                    website = COALESCE(excluded.website, hospitals.website),
                    hospital_type = COALESCE(excluded.hospital_type, hospitals.hospital_type),
                    ownership = COALESCE(excluded.ownership, hospitals.ownership),
                    source_url = COALESCE(excluded.source_url, hospitals.source_url)
                RETURNING id
                """,
                fields,
            ).fetchone()
        if row is None:
            raise StoreError("failed to upsert hospital")
        return int(row["id"])

    def get_hospital(self, hospital_id: int) -> Hospital | None:
        row = self._conn.execute(
            "SELECT * FROM hospitals WHERE id = ?", (hospital_id,)
        ).fetchone()
        return mappers.hospital_from_row(row) if row else None

    def find_hospitals(self, query: str = "", limit: int = 50) -> list[Hospital]:
        if query:
            rows = self._conn.execute(
                "SELECT * FROM hospitals WHERE name LIKE ? OR city LIKE ? OR state LIKE ? "
                "ORDER BY name LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM hospitals ORDER BY name LIMIT ?", (limit,)
            ).fetchall()
        return [mappers.hospital_from_row(r) for r in rows]

    # ---------------------------------------------------------------- contacts
    def save_contacts(self, contacts: list[Contact]) -> list[int]:
        ids: list[int] = []
        with self._tx():
            for c in contacts:
                row = self._conn.execute(
                    """
                    INSERT INTO contacts
                        (hospital_id, name, title, department, email, country, timezone,
                         lawful_basis, source_url, confidence, fit_score, fit_reasons,
                         status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (email, hospital_id) DO UPDATE SET
                        name = COALESCE(excluded.name, contacts.name),
                        title = COALESCE(excluded.title, contacts.title),
                        department = COALESCE(excluded.department, contacts.department),
                        country = COALESCE(excluded.country, contacts.country),
                        timezone = COALESCE(excluded.timezone, contacts.timezone),
                        lawful_basis = CASE
                            WHEN excluded.lawful_basis != 'unknown' THEN excluded.lawful_basis
                            ELSE contacts.lawful_basis
                        END,
                        source_url = COALESCE(excluded.source_url, contacts.source_url),
                        confidence = MAX(excluded.confidence, contacts.confidence)
                    RETURNING id
                    """,
                    (
                        c.hospital_id,
                        c.name,
                        c.title,
                        c.department,
                        c.email_value,
                        c.country,
                        c.timezone,
                        c.lawful_basis,
                        c.source_url,
                        c.confidence,
                        c.fit_score,
                        json.dumps(c.fit_reasons),
                        str(c.status),
                        mappers.dt(c.created_at),
                    ),
                ).fetchone()
                if row is not None:
                    ids.append(int(row["id"]))
        return ids

    def get_contact(self, contact_id: int) -> Contact | None:
        row = self._conn.execute(
            """
            SELECT c.*, h.name AS hospital_name FROM contacts c
            LEFT JOIN hospitals h ON h.id = c.hospital_id
            WHERE c.id = ?
            """,
            (contact_id,),
        ).fetchone()
        return mappers.contact_from_row(row) if row else None

    def find_contacts(
        self,
        status: ContactStatus | None = None,
        with_email_only: bool = True,
        scored_only: bool = False,
        limit: int = 100,
    ) -> list[Contact]:
        where: list[str] = []
        params: list = []
        if status is not None:
            where.append("c.status = ?")
            params.append(str(status))
        if with_email_only:
            where.append("c.email IS NOT NULL")
        if scored_only:
            where.append("c.fit_score IS NOT NULL")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT c.*, h.name AS hospital_name FROM contacts c
            LEFT JOIN hospitals h ON h.id = c.hospital_id
            {clause}
            ORDER BY COALESCE(c.fit_score, 0) DESC, c.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [mappers.contact_from_row(r) for r in rows]

    def update_contact_fit(
        self, contact_id: int, score: float, reasons: list[str], status: ContactStatus
    ) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE contacts SET fit_score = ?, fit_reasons = ?, status = ? WHERE id = ?",
                (score, json.dumps(reasons), str(status), contact_id),
            )

    def set_contact_status(self, contact_id: int, status: ContactStatus) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE contacts SET status = ? WHERE id = ?", (str(status), contact_id)
            )

    def update_contact_compliance(
        self,
        contact_id: int,
        country: str | None,
        timezone: str | None,
        lawful_basis: str,
    ) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE contacts SET country = ?, timezone = ?, lawful_basis = ? WHERE id = ?",
                (country, timezone, lawful_basis, contact_id),
            )

    # --------------------------------------------------------------- campaigns
    def upsert_campaign(self, campaign: Campaign) -> int:
        with self._tx():
            row = self._conn.execute(
                """
                INSERT INTO campaigns (name, goal, tone, language, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (name) DO UPDATE SET
                    goal = excluded.goal, tone = excluded.tone, language = excluded.language
                RETURNING id
                """,
                (
                    campaign.name,
                    campaign.goal,
                    campaign.tone,
                    campaign.language,
                    mappers.dt(campaign.created_at),
                ),
            ).fetchone()
        if row is None:
            raise StoreError("failed to upsert campaign")
        return int(row["id"])

    def get_campaign(self, name: str) -> Campaign | None:
        row = self._conn.execute("SELECT * FROM campaigns WHERE name = ?", (name,)).fetchone()
        return mappers.campaign_from_row(row) if row else None

    def get_campaign_by_id(self, campaign_id: int) -> Campaign | None:
        row = self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        return mappers.campaign_from_row(row) if row else None

    def find_campaigns(self, limit: int = 50) -> list[Campaign]:
        rows = self._conn.execute(
            "SELECT * FROM campaigns ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [mappers.campaign_from_row(row) for row in rows]

    # ------------------------------------------------------------------ drafts
    def save_draft(self, draft: Draft) -> int:
        with self._tx():
            row = self._conn.execute(
                """
                INSERT INTO drafts
                    (invocation_id, contact_id, campaign_id, subject, body_text, body_html,
                     rationale, confidence, provider, status, created_at, approved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    draft.invocation_id,
                    draft.contact_id,
                    draft.campaign_id,
                    draft.subject,
                    draft.body_text,
                    draft.body_html,
                    draft.rationale,
                    draft.confidence,
                    draft.provider,
                    str(draft.status),
                    mappers.dt(draft.created_at),
                    mappers.dt(draft.approved_at),
                ),
            ).fetchone()
        if row is None:
            raise StoreError("failed to save draft")
        return int(row["id"])

    def get_draft(self, draft_id: int) -> Draft | None:
        row = self._conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return mappers.draft_from_row(row) if row else None

    def find_drafts(self, status: DraftStatus | None = None, limit: int = 100) -> list[Draft]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM drafts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM drafts WHERE status = ? ORDER BY id DESC LIMIT ?",
                (str(status), limit),
            ).fetchall()
        return [mappers.draft_from_row(r) for r in rows]

    def set_draft_status(self, draft_id: int, status: DraftStatus) -> None:
        approved_at = mappers.dt(utcnow()) if status == DraftStatus.APPROVED else None
        with self._tx():
            self._conn.execute(
                "UPDATE drafts SET status = ?, approved_at = COALESCE(?, approved_at) WHERE id = ?",
                (str(status), approved_at, draft_id),
            )

    def update_draft_body(
        self, draft_id: int, subject: str, body_text: str, body_html: str | None
    ) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE drafts SET subject = ?, body_text = ?, body_html = ? WHERE id = ?",
                (subject, body_text, body_html, draft_id),
            )

    # ------------------------------------------------------------------- sends
    def record_send(self, send: Send) -> int:
        with self._tx():
            row = self._conn.execute(
                """
                INSERT INTO sends
                    (invocation_id, draft_id, contact_id, message_id, to_email, status, error, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    send.invocation_id,
                    send.draft_id,
                    send.contact_id,
                    send.message_id,
                    send.to_email,
                    str(send.status),
                    send.error,
                    mappers.dt(send.sent_at),
                ),
            ).fetchone()
        if row is None:
            raise StoreError("failed to record send")
        return int(row["id"])

    def sends_today(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM sends WHERE date(sent_at) = date('now') AND status = ?",
            (str(SendStatus.SENT),),
        ).fetchone()
        return int(row["n"]) if row else 0

    def sends_today_for_domain(self, domain: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS n FROM sends s
            JOIN contacts c ON c.id = s.contact_id
            WHERE date(s.sent_at) = date('now')
              AND s.status = ?
              AND c.email LIKE '%@' || ?
            """,
            (str(SendStatus.SENT), domain),
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------ suppressions
    def is_suppressed(self, email: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM suppressions WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return row is not None

    def add_suppression(self, email: str, reason: str = "") -> None:
        with self._tx():
            self._conn.execute(
                "INSERT OR REPLACE INTO suppressions (email, reason, created_at) VALUES (?, ?, ?)",
                (email.strip().lower(), reason, mappers.dt(utcnow())),
            )

    def list_suppressions(self, limit: int = 200) -> list[Suppression]:
        rows = self._conn.execute(
            "SELECT * FROM suppressions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            Suppression(
                email=r["email"],
                reason=r["reason"],
                created_at=mappers.parse_dt(r["created_at"]) or utcnow(),
            )
            for r in rows
        ]

    # ------------------------------------------------------------- invocations
    def record_invocation(self, invocation: Invocation) -> None:
        with self._tx():
            self._conn.execute(
                """
                INSERT INTO invocations
                    (id, agent_name, campaign_id, status, input_json, output_json, error,
                     started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invocation.id,
                    invocation.agent_name,
                    invocation.campaign_id,
                    str(invocation.status),
                    json.dumps(invocation.input_json),
                    json.dumps(invocation.output_json) if invocation.output_json else None,
                    invocation.error,
                    mappers.dt(invocation.started_at),
                    mappers.dt(invocation.finished_at),
                ),
            )

    def finish_invocation(
        self,
        invocation_id: str,
        status: InvocationStatus,
        output: dict | None = None,
        error: str | None = None,
    ) -> None:
        with self._tx():
            self._conn.execute(
                """
                UPDATE invocations
                SET status = ?, output_json = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    str(status),
                    json.dumps(output) if output is not None else None,
                    error,
                    mappers.dt(utcnow()),
                    invocation_id,
                ),
            )

    def find_invocations(self, limit: int = 20) -> list[Invocation]:
        rows = self._conn.execute(
            "SELECT * FROM invocations ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [mappers.invocation_from_row(r) for r in rows]

    def get_invocation(self, invocation_id: str) -> Invocation | None:
        row = self._conn.execute(
            "SELECT * FROM invocations WHERE id = ?", (invocation_id,)
        ).fetchone()
        return mappers.invocation_from_row(row) if row else None

    # ------------------------------------------------------------- data rights
    def erase_contact(self, email: str) -> dict:
        """Delete all stored data for an email; keep a minimal suppression record."""
        email = email.strip().lower()
        with self._tx():
            rows = self._conn.execute(
                "SELECT id FROM contacts WHERE email = ?", (email,)
            ).fetchall()
            contact_ids = [int(row["id"]) for row in rows]
            drafts_deleted = 0
            sends_deleted = 0
            if contact_ids:
                placeholders = ",".join("?" for _ in contact_ids)
                sends_deleted = self._conn.execute(
                    f"DELETE FROM sends WHERE contact_id IN ({placeholders})", contact_ids
                ).rowcount
                drafts_deleted = self._conn.execute(
                    f"DELETE FROM drafts WHERE contact_id IN ({placeholders})", contact_ids
                ).rowcount
                self._conn.execute(
                    f"DELETE FROM contacts WHERE id IN ({placeholders})", contact_ids
                )
            self._conn.execute(
                "INSERT OR REPLACE INTO suppressions (email, reason, created_at) VALUES (?, ?, ?)",
                (email, "erasure", mappers.dt(utcnow())),
            )
        return {
            "email": email,
            "contacts_deleted": len(contact_ids),
            "drafts_deleted": drafts_deleted,
            "sends_deleted": sends_deleted,
        }

    def purge_older_than(self, days: int) -> dict:
        """Delete records older than the retention window."""
        cutoff = mappers.dt(utcnow() - timedelta(days=max(0, days)))
        with self._tx():
            sends_deleted = self._conn.execute(
                "DELETE FROM sends WHERE sent_at < ?", (cutoff,)
            ).rowcount
            drafts_deleted = self._conn.execute(
                "DELETE FROM drafts WHERE created_at < ?", (cutoff,)
            ).rowcount
            contacts_deleted = self._conn.execute(
                "DELETE FROM contacts WHERE created_at < ? AND id NOT IN ("
                "SELECT contact_id FROM drafts UNION SELECT contact_id FROM sends)",
                (cutoff,),
            ).rowcount
        return {
            "cutoff": cutoff,
            "contacts_deleted": contacts_deleted,
            "drafts_deleted": drafts_deleted,
            "sends_deleted": sends_deleted,
        }

    def export_contact(self, email: str) -> dict:
        """Return every stored record tied to an email address (right of access)."""
        email = email.strip().lower()
        rows = self._conn.execute(
            """
            SELECT c.*, h.name AS hospital_name FROM contacts c
            LEFT JOIN hospitals h ON h.id = c.hospital_id
            WHERE c.email = ?
            """,
            (email,),
        ).fetchall()
        contacts = [mappers.contact_from_row(row) for row in rows]
        contact_ids = [contact.id for contact in contacts if contact.id is not None]
        drafts: list = []
        sends: list = []
        if contact_ids:
            placeholders = ",".join("?" for _ in contact_ids)
            drafts = [
                mappers.draft_from_row(row)
                for row in self._conn.execute(
                    f"SELECT * FROM drafts WHERE contact_id IN ({placeholders})",
                    contact_ids,
                ).fetchall()
            ]
            sends = [
                mappers.send_from_row(row)
                for row in self._conn.execute(
                    f"SELECT * FROM sends WHERE contact_id IN ({placeholders})",
                    contact_ids,
                ).fetchall()
            ]
        hospitals = []
        for hospital_id in {c.hospital_id for c in contacts if c.hospital_id is not None}:
            hospital = self.get_hospital(hospital_id)
            if hospital is not None:
                hospitals.append(hospital)
        sends_payload = []
        for send in sends:
            entry = send.model_dump(mode="json")
            entry["attachments"] = (
                self.find_sent_attachments(send.id) if send.id is not None else []
            )
            sends_payload.append(entry)
        return {
            "email": email,
            "contacts": [c.model_dump(mode="json") for c in contacts],
            "hospitals": [h.model_dump(mode="json") for h in hospitals],
            "drafts": [d.model_dump(mode="json") for d in drafts],
            "sends": sends_payload,
        }

    # ------------------------------------------------------------------- users
    def count_users(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"]) if row else 0

    def create_user(self, username: str, password_hash: str) -> int:
        now = mappers.dt(utcnow())
        with self._tx():
            row = self._conn.execute(
                "INSERT INTO users (username, password_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) RETURNING id",
                (username.strip(), password_hash, now, now),
            ).fetchone()
        if row is None:
            raise StoreError("failed to create user")
        return int(row["id"])

    def find_user(self, username: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        return mappers.user_from_row(row) if row else None

    def update_user_password(self, username: str, password_hash: str) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
                (password_hash, mappers.dt(utcnow()), username.strip()),
            )

    # ------------------------------------------------------------- attachments
    def save_attachment(self, attachment: Attachment) -> int:
        existing = self.find_attachment_by_sha(attachment.sha256)
        if existing is not None:
            return int(existing.id or 0)
        with self._tx():
            row = self._conn.execute(
                """
                INSERT INTO attachments (filename, content_type, size, sha256, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?) RETURNING id
                """,
                (
                    attachment.filename,
                    attachment.content_type,
                    attachment.size,
                    attachment.sha256,
                    attachment.data or b"",
                    mappers.dt(attachment.created_at),
                ),
            ).fetchone()
        if row is None:
            raise StoreError("failed to save attachment")
        return int(row["id"])

    def get_attachment(self, attachment_id: int) -> Attachment | None:
        row = self._conn.execute(
            "SELECT id, filename, content_type, size, sha256, created_at "
            "FROM attachments WHERE id = ?",
            (attachment_id,),
        ).fetchone()
        return mappers.attachment_from_row(row) if row else None

    def get_attachment_data(self, attachment_id: int) -> bytes | None:
        row = self._conn.execute(
            "SELECT data FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        return bytes(row["data"]) if row and row["data"] is not None else None

    def find_attachment_by_sha(self, sha256: str) -> Attachment | None:
        row = self._conn.execute(
            "SELECT id, filename, content_type, size, sha256, created_at "
            "FROM attachments WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
        return mappers.attachment_from_row(row) if row else None

    def list_attachments(self, limit: int = 200) -> list[Attachment]:
        rows = self._conn.execute(
            "SELECT id, filename, content_type, size, sha256, created_at "
            "FROM attachments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [mappers.attachment_from_row(row) for row in rows]

    def delete_attachment(self, attachment_id: int) -> bool:
        referenced = self._conn.execute(
            "SELECT 1 FROM sent_attachments WHERE attachment_id = ? LIMIT 1",
            (attachment_id,),
        ).fetchone()
        if referenced is not None:
            return False
        with self._tx():
            self._conn.execute(
                "DELETE FROM draft_attachments WHERE attachment_id = ?", (attachment_id,)
            )
            self._conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        return True

    def attach_to_draft(self, draft_id: int, attachment_id: int) -> None:
        with self._tx():
            self._conn.execute(
                "INSERT OR IGNORE INTO draft_attachments (draft_id, attachment_id) VALUES (?, ?)",
                (draft_id, attachment_id),
            )

    def detach_from_draft(self, draft_id: int, attachment_id: int) -> None:
        with self._tx():
            self._conn.execute(
                "DELETE FROM draft_attachments WHERE draft_id = ? AND attachment_id = ?",
                (draft_id, attachment_id),
            )

    def find_draft_attachments(self, draft_id: int) -> list[Attachment]:
        rows = self._conn.execute(
            """
            SELECT a.id, a.filename, a.content_type, a.size, a.sha256, a.created_at
            FROM draft_attachments da
            JOIN attachments a ON a.id = da.attachment_id
            WHERE da.draft_id = ?
            ORDER BY a.id
            """,
            (draft_id,),
        ).fetchall()
        return [mappers.attachment_from_row(row) for row in rows]

    def record_sent_attachments(self, send_id: int, attachments: list[Attachment]) -> None:
        with self._tx():
            for attachment in attachments:
                self._conn.execute(
                    "INSERT OR REPLACE INTO sent_attachments "
                    "(send_id, attachment_id, filename, size) VALUES (?, ?, ?, ?)",
                    (send_id, attachment.id, attachment.filename, attachment.size),
                )

    def find_sent_attachments(self, send_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT attachment_id, filename, size FROM sent_attachments "
            "WHERE send_id = ? ORDER BY filename",
            (send_id,),
        ).fetchall()
        return [
            {
                "attachment_id": row["attachment_id"],
                "filename": row["filename"],
                "size": row["size"],
            }
            for row in rows
        ]

    # ----------------------------------------------------------------- summary
    def summary(self) -> dict:
        def scalar(sql: str, params: tuple = ()) -> int:
            row = self._conn.execute(sql, params).fetchone()
            return int(row["n"]) if row else 0

        return {
            "hospitals": scalar("SELECT COUNT(*) AS n FROM hospitals"),
            "contacts": scalar("SELECT COUNT(*) AS n FROM contacts"),
            "contacts_with_email": scalar(
                "SELECT COUNT(*) AS n FROM contacts WHERE email IS NOT NULL"
            ),
            "contacts_scored": scalar(
                "SELECT COUNT(*) AS n FROM contacts WHERE fit_score IS NOT NULL"
            ),
            "drafts_pending": scalar(
                "SELECT COUNT(*) AS n FROM drafts WHERE status = ?", (str(DraftStatus.PENDING),)
            ),
            "drafts_approved": scalar(
                "SELECT COUNT(*) AS n FROM drafts WHERE status = ?", (str(DraftStatus.APPROVED),)
            ),
            "sent_today": self.sends_today(),
            "sent_total": scalar(
                "SELECT COUNT(*) AS n FROM sends WHERE status = ?", (str(SendStatus.SENT),)
            ),
            "suppressed": scalar("SELECT COUNT(*) AS n FROM suppressions"),
        }
