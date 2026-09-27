from electivesmed.services.extraction import extract_contacts

from tests import constants as C
from tests.fakes import FakeLlm


def test_extract_requires_llm(container):
    container.llm = FakeLlm(available=False)

    result = extract_contacts(container, "page text")

    assert "error" in result


def test_extract_persists_normalized_contacts(container, extraction_response):
    container.llm = FakeLlm(json_response=extraction_response)

    result = extract_contacts(
        container,
        "raw page text",
        source_url="http://source.test",
        hospital_name=C.HOSPITAL_NAME,
    )

    assert result["hospital_name"] == C.HOSPITAL_NAME
    assert result["extracted"] == 2
    assert len(result["saved_ids"]) == 2
    assert result["contacts"][0]["email"] == C.CONTACT_EMAIL
    assert container.dao.summary()["contacts"] == 2


def test_extract_passes_hospital_id(container, seeded):
    container.llm = FakeLlm(json_response={"contacts": [{"name": "A"}]})

    result = extract_contacts(container, "text", hospital_id=seeded["hospital_id"])
    contact = container.dao.get_contact(result["saved_ids"][0])

    assert contact.hospital_id == seeded["hospital_id"]


def test_extract_handles_empty_response(container):
    container.llm = FakeLlm(json_response={})

    result = extract_contacts(container, "text")

    assert result["extracted"] == 0
    assert result["contacts"] == []
