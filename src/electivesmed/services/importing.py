"""Activity: import contacts from CSV text (shared by CLI and web clients)."""

import csv
import io

from ..converters.contact import contact_from_input
from ..models.entities import Hospital
from ..models.enums import SourceType
from ..models.views import ContactInput
from .ingestion.parsers.common import cell


def import_contacts_csv(
    container,
    text: str,
    *,
    source_url: str = "",
    hospital_name: str = "",
    country: str = "",
) -> dict:
    """Parse contact rows, resolve hospitals, persist contacts. Returns counts."""
    reader = csv.DictReader(io.StringIO(text))
    hospital_ids: dict[str, int] = {}
    contacts = []
    for row in reader:
        cleaned = {
            (key or "").strip().lower(): cell(value) for key, value in row.items()
        }
        if not (cleaned.get("name") or cleaned.get("email")):
            continue
        resolved_hospital = (
            cleaned.get("hospital_name") or cleaned.get("hospital") or hospital_name
        )
        row_country = cleaned.get("country") or country
        hospital_id = None
        if resolved_hospital:
            key = resolved_hospital.lower()
            if key not in hospital_ids:
                hospital_ids[key] = container.dao.upsert_hospital(
                    Hospital(
                        name=resolved_hospital,
                        city=cleaned.get("city") or None,
                        state=cleaned.get("state") or None,
                        country=row_country,
                        website=cleaned.get("website") or None,
                        source_type=SourceType.CSV,
                        source_url=source_url,
                    )
                )
            hospital_id = hospital_ids[key]
        contacts.append(
            contact_from_input(
                ContactInput(
                    name=cleaned.get("name") or None,
                    title=cleaned.get("title") or None,
                    department=cleaned.get("department") or None,
                    email=cleaned.get("email") or None,
                    hospital_name=resolved_hospital or None,
                    country=row_country or None,
                    timezone=cleaned.get("timezone") or None,
                    lawful_basis=cleaned.get("lawful_basis") or None,
                    source_url=source_url or None,
                ),
                hospital_id,
            )
        )
    ids = container.dao.save_contacts(contacts)
    return {"rows_seen": len(contacts), "saved": len(ids)}
