from electivesmed.models.entities import Contact, Hospital
from electivesmed.models.enums import SourceType
from electivesmed.models.values import EmailAddress

from tests import constants as C


def test_hospital_defaults():
    hospital = Hospital(name=C.HOSPITAL_NAME)

    assert hospital.country == ""
    assert hospital.source_type is SourceType.MANUAL
    assert hospital.created_at.tzinfo is not None


def test_contact_email_value():
    with_email = Contact(name="A", email=EmailAddress(value=C.CONTACT_EMAIL))
    without_email = Contact(name="B")

    assert with_email.email_value == C.CONTACT_EMAIL
    assert without_email.email_value is None
