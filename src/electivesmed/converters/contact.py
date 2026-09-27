"""Contact domain ↔ client DTO mapping."""

from ..compliance import DEFAULT_LAWFUL_BASIS
from ..models.entities import Contact
from ..models.values import EmailAddress
from ..models.views import ContactInput, ContactView


def contact_to_view(contact: Contact) -> ContactView:
    return ContactView(
        id=contact.id,
        hospital=contact.hospital_name,
        name=contact.name,
        title=contact.title,
        department=contact.department,
        email=contact.email_value,
        fit_score=contact.fit_score,
        fit_percent=round(contact.fit_score * 100) if contact.fit_score is not None else None,
        status=str(contact.status),
        source_url=contact.source_url,
    )


def contact_from_input(data: ContactInput, hospital_id: int | None) -> Contact:
    email = None
    if data.email:
        try:
            email = EmailAddress(value=data.email)
        except ValueError:
            email = None
    return Contact(
        hospital_id=hospital_id,
        name=data.name,
        title=data.title,
        department=data.department,
        email=email,
        country=data.country,
        timezone=data.timezone,
        lawful_basis=data.lawful_basis or DEFAULT_LAWFUL_BASIS,
        source_url=data.source_url,
    )
