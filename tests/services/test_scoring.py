from electivesmed.models.entities import Contact
from electivesmed.models.values import EmailAddress
from electivesmed.services.scoring import score_contacts

from tests import constants as C
from tests.fakes import FakeLlm


def test_score_without_contacts_returns_note(container):
    result = score_contacts(container)

    assert result["scored"] == 0
    assert "no contacts" in result["note"]


def test_score_heuristic_persists_fit(container, seeded):
    container.llm = FakeLlm(available=False)

    result = score_contacts(container, limit=10)

    assert result["method"] == "heuristic"
    assert result["scored"] == 1
    contact = container.dao.get_contact(seeded["contact_id"])
    assert contact.fit_score is not None
    assert container.dao.summary()["contacts_scored"] == 1


def test_score_llm_uses_provider_scores(container, seeded):
    container.llm = FakeLlm(
        json_response={
            "scores": [{"id": seeded["contact_id"], "score": 0.9, "reasons": ["great fit"]}]
        }
    )

    result = score_contacts(container, limit=10)
    contact = container.dao.get_contact(seeded["contact_id"])

    assert result["method"] == "llm"
    assert contact.fit_score == 0.9
    assert contact.fit_reasons == ["great fit"]


def test_score_llm_invalid_entries_fall_back_to_heuristic(container, seeded):
    container.llm = FakeLlm(
        json_response={
            "scores": [
                {"id": "bad", "score": 0.5},
                {"id": seeded["contact_id"], "score": "not-a-number"},
            ]
        }
    )

    result = score_contacts(container, limit=10)
    contact = container.dao.get_contact(seeded["contact_id"])

    assert result["method"] == "llm"
    assert contact.fit_score is not None
    assert contact.fit_score != 0.9


def test_score_skips_contacts_without_id(container, monkeypatch):
    container.llm = FakeLlm(available=False)
    monkeypatch.setattr(
        container.dao,
        "get_contact",
        lambda contact_id: Contact(name="No Id", email=EmailAddress(value=C.CONTACT_EMAIL)),
    )

    result = score_contacts(container, contact_ids=[1])

    assert result["scored"] == 0


def test_score_explicit_contact_ids(container, seeded):
    container.llm = FakeLlm(available=False)

    result = score_contacts(container, contact_ids=[seeded["contact_id"]])

    assert result["scored"] == 1
    assert result["top"][0]["id"] == seeded["contact_id"]


def test_score_top_is_sorted_descending(container, seeded):
    container.dao.save_contacts(
        [
            Contact(
                hospital_id=seeded["hospital_id"],
                name="John Smith",
                title="Cardiologist",
                email=EmailAddress(value=C.CONTACT_EMAIL_ALT),
            )
        ]
    )

    result = score_contacts(container, limit=10)

    scores = [row["fit_score"] for row in result["top"]]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == 2
