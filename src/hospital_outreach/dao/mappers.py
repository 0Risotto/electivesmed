"""Row ↔ domain model mapping. No queries, no I/O."""

import json
import sqlite3
from datetime import datetime

from ..models.entities import Campaign, Contact, Draft, Hospital
from ..models.enums import ContactStatus, DraftStatus, InvocationStatus, SourceType
from ..models.invocation import Invocation
from ..models.values import EmailAddress
from ..utils.time import utcnow


def dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def hospital_from_row(row: sqlite3.Row) -> Hospital:
    return Hospital(
        id=row["id"],
        name=row["name"],
        city=row["city"],
        state=row["state"],
        country=row["country"] or "US",
        website=row["website"],
        hospital_type=row["hospital_type"],
        ownership=row["ownership"],
        beds=row["beds"],
        source_type=SourceType(row["source_type"]),
        source_url=row["source_url"],
        created_at=parse_dt(row["created_at"]) or utcnow(),
    )


def contact_from_row(row: sqlite3.Row) -> Contact:
    email = EmailAddress(value=row["email"]) if row["email"] else None
    return Contact(
        id=row["id"],
        hospital_id=row["hospital_id"],
        hospital_name=row["hospital_name"] if "hospital_name" in row.keys() else None,
        name=row["name"],
        title=row["title"],
        department=row["department"],
        email=email,
        source_url=row["source_url"],
        confidence=row["confidence"],
        fit_score=row["fit_score"],
        fit_reasons=json.loads(row["fit_reasons"] or "[]"),
        status=ContactStatus(row["status"]),
        created_at=parse_dt(row["created_at"]) or utcnow(),
    )


def draft_from_row(row: sqlite3.Row) -> Draft:
    return Draft(
        id=row["id"],
        invocation_id=row["invocation_id"],
        contact_id=row["contact_id"],
        campaign_id=row["campaign_id"],
        subject=row["subject"],
        body_text=row["body_text"],
        body_html=row["body_html"],
        rationale=row["rationale"],
        confidence=row["confidence"],
        provider=row["provider"],
        status=DraftStatus(row["status"]),
        created_at=parse_dt(row["created_at"]) or utcnow(),
        approved_at=parse_dt(row["approved_at"]),
    )


def campaign_from_row(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=row["id"],
        name=row["name"],
        goal=row["goal"],
        tone=row["tone"],
        language=row["language"],
        created_at=parse_dt(row["created_at"]) or utcnow(),
    )


def invocation_from_row(row: sqlite3.Row) -> Invocation:
    return Invocation(
        id=row["id"],
        agent_name=row["agent_name"],
        campaign_id=row["campaign_id"],
        status=InvocationStatus(row["status"]),
        input_json=json.loads(row["input_json"] or "{}"),
        output_json=json.loads(row["output_json"]) if row["output_json"] else None,
        error=row["error"],
        started_at=parse_dt(row["started_at"]) or utcnow(),
        finished_at=parse_dt(row["finished_at"]),
    )
