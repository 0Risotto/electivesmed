from electivesmed.components.extraction import MAX_CONTACTS_PER_PAGE, ContactNormalizer

from tests import constants as C


def test_normalize_keeps_valid_and_cleans_invalid(extraction_response):
    contacts = ContactNormalizer().normalize(
        extraction_response, hospital_id=7, source_url="http://source.test"
    )

    assert len(contacts) == 2
    first = contacts[0]
    assert first.name == C.CONTACT_NAME
    assert str(first.email) == C.CONTACT_EMAIL
    assert first.hospital_id == 7
    assert first.source_url == "http://source.test"
    assert first.confidence == 0.9

    second = contacts[1]
    assert second.email is None
    assert second.confidence == 0.0


def test_normalize_clamps_confidence():
    data = {"contacts": [{"name": "A", "confidence": 5}, {"name": "B", "confidence": -3}]}
    contacts = ContactNormalizer().normalize(data)

    assert contacts[0].confidence == 1.0
    assert contacts[1].confidence == 0.0


def test_normalize_respects_page_limit():
    data = {"contacts": [{"name": f"Person {i}"} for i in range(MAX_CONTACTS_PER_PAGE + 5)]}
    assert len(ContactNormalizer().normalize(data)) == MAX_CONTACTS_PER_PAGE


def test_normalize_handles_missing_contacts_key():
    assert ContactNormalizer().normalize({}) == []


def test_normalize_cleans_whitespace_only_fields():
    data = {"contacts": [{"name": " A ", "title": "  ", "department": "Cardiology"}]}
    contact = ContactNormalizer().normalize(data)[0]

    assert contact.title is None
    assert contact.department == "Cardiology"
