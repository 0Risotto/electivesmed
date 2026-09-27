from electivesmed.converters.contact import contact_from_input, contact_to_view
from electivesmed.models.entities import Contact
from electivesmed.models.enums import ContactStatus
from electivesmed.models.values import EmailAddress
from electivesmed.models.views import ContactInput

from tests import constants as C


def test_contact_to_view_maps_all_fields():
    contact = Contact(
        id=1,
        hospital_id=2,
        hospital_name=C.HOSPITAL_NAME,
        name=C.CONTACT_NAME,
        title=C.CONTACT_TITLE,
        department="Cardiology",
        email=EmailAddress(value=C.CONTACT_EMAIL),
        fit_score=0.75,
        status=ContactStatus.SCORED,
    )

    view = contact_to_view(contact)

    assert view.id == 1
    assert view.hospital == C.HOSPITAL_NAME
    assert view.email == C.CONTACT_EMAIL
    assert view.fit_percent == 75
    assert view.status == "scored"


def test_contact_to_view_without_email_or_score():
    view = contact_to_view(Contact(name="Anonymous"))

    assert view.email is None
    assert view.fit_percent is None


def test_contact_from_input_valid_email():
    contact = contact_from_input(
        ContactInput(name=C.CONTACT_NAME, email=C.CONTACT_EMAIL), hospital_id=3
    )

    assert contact.hospital_id == 3
    assert str(contact.email) == C.CONTACT_EMAIL


def test_contact_from_input_invalid_email_is_dropped():
    contact = contact_from_input(ContactInput(name="A", email="not-an-email"), hospital_id=None)

    assert contact.email is None


def test_contact_from_input_without_email():
    assert contact_from_input(ContactInput(name="A"), hospital_id=None).email is None


def test_contact_from_input_maps_compliance_fields():
    contact = contact_from_input(
        ContactInput(
            name="A",
            country="DE",
            timezone="Europe/Berlin",
            lawful_basis="consent",
        ),
        hospital_id=None,
    )

    assert contact.country == "DE"
    assert contact.timezone == "Europe/Berlin"
    assert contact.lawful_basis == "consent"


def test_contact_from_input_defaults_to_unknown_basis():
    assert contact_from_input(ContactInput(name="A"), hospital_id=None).lawful_basis == "unknown"


def test_contact_to_view_includes_country():
    view = contact_to_view(Contact(name="A", country="DE"))

    assert view.country == "DE"
