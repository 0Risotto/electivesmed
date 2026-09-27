from electivesmed.builders.payloads import build_payload

from tests import constants as C


def _draft(container, seeded, body=C.DRAFT_BODY):
    draft = container.dao.get_draft(seeded["draft_id"])
    draft.body_text = body
    return draft


def test_payload_appends_opt_out(container, seeded):
    payload = build_payload(
        _draft(container, seeded), container.dao.get_contact(seeded["contact_id"]), C.SENDER_EMAIL
    )

    assert C.OPT_OUT in payload.body_text
    assert payload.to == C.CONTACT_EMAIL
    assert payload.from_email == C.SENDER_EMAIL


def test_payload_does_not_duplicate_opt_out(container, seeded):
    body = f"{C.DRAFT_BODY}\n\n{C.OPT_OUT}"
    payload = build_payload(
        _draft(container, seeded, body), container.dao.get_contact(seeded["contact_id"]), C.SENDER_EMAIL
    )

    assert payload.body_text.count(C.OPT_OUT) == 1


def test_payload_can_skip_opt_out(container, seeded):
    payload = build_payload(
        _draft(container, seeded),
        container.dao.get_contact(seeded["contact_id"]),
        C.SENDER_EMAIL,
        include_opt_out=False,
    )

    assert C.OPT_OUT not in payload.body_text


def test_payload_with_reply_to_adds_unsubscribe_header(container, seeded):
    payload = build_payload(
        _draft(container, seeded),
        container.dao.get_contact(seeded["contact_id"]),
        C.SENDER_EMAIL,
        reply_to=C.REPLY_TO,
    )

    assert payload.reply_to == C.REPLY_TO
    assert payload.headers["List-Unsubscribe"].startswith(f"<mailto:{C.REPLY_TO}")


def test_payload_without_reply_to_has_no_headers(container, seeded):
    payload = build_payload(
        _draft(container, seeded), container.dao.get_contact(seeded["contact_id"]), C.SENDER_EMAIL
    )

    assert payload.headers == {}


def test_payload_appends_postal_footer(container, seeded):
    payload = build_payload(
        _draft(container, seeded),
        container.dao.get_contact(seeded["contact_id"]),
        C.SENDER_EMAIL,
        postal_address="1 Main St, Fresno, CA",
        sender_name="Dr Example",
        organization="Example Clinic",
    )

    assert "Dr Example" in payload.body_text
    assert "Example Clinic" in payload.body_text
    assert "1 Main St, Fresno, CA" in payload.body_text


def test_payload_without_postal_address_has_no_footer(container, seeded):
    payload = build_payload(
        _draft(container, seeded), container.dao.get_contact(seeded["contact_id"]), C.SENDER_EMAIL
    )

    assert "1 Main St" not in payload.body_text
