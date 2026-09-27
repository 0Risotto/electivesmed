from hospital_outreach.builders.payloads import build_payload
from hospital_outreach.compliance import OPT_OUT_SENTENCE
from hospital_outreach.components.policy import PolicyGate
from hospital_outreach.models.entities import SendReceipt
from hospital_outreach.models.enums import DraftStatus, SendStatus
from hospital_outreach.services.sending import send_one


class FakeMail:
    def __init__(self):
        self.calls = []

    def send(self, payload, dry_run=True):
        self.calls.append((payload, dry_run))
        return SendReceipt(
            message_id="<test@local>",
            accepted=True,
            status=SendStatus.DRY_RUN if dry_run else SendStatus.SENT,
            dry_run=dry_run,
        )

    def close(self):
        pass


def _gate(container):
    return PolicyGate(container.dao, container.settings)


def test_pending_draft_is_denied(container, seeded):
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])
    decision = _gate(container).check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "approval" in decision.reason


def test_approved_draft_allowed_dry_run(container, seeded):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])
    decision = _gate(container).check_send(draft, contact, dry_run=True)
    assert decision.allowed
    assert any("opt-out" in w for w in decision.warnings)


def test_suppressed_email_is_denied(container, seeded):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    container.dao.add_suppression("jane.doe@testhospital.org", "unsubscribe")
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])
    decision = _gate(container).check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "suppression" in decision.reason


def test_daily_cap_blocks_real_send(container, seeded):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    container.settings.limits.daily_send_cap = 0
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])
    decision = _gate(container).check_send(draft, contact, dry_run=False)
    assert not decision.allowed
    assert "cap" in decision.reason


def test_spam_words_block(container, seeded):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    draft = container.dao.get_draft(seeded["draft_id"])
    draft.body_text = "This is a free guarantee, act now!"
    contact = container.dao.get_contact(seeded["contact_id"])
    decision = _gate(container).check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "spam" in decision.reason


def test_build_payload_appends_opt_out(container, seeded):
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])
    payload = build_payload(draft, contact, from_email="me@example.org")
    assert OPT_OUT_SENTENCE in payload.body_text
    assert payload.to == "jane.doe@testhospital.org"


def test_send_one_end_to_end_with_fake_mail(container, seeded, invocation_ctx):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.APPROVED)
    fake = FakeMail()
    container.mail = fake
    result = send_one(container, seeded["draft_id"], dry_run=True)
    assert result["status"] == "dry_run"
    assert len(fake.calls) == 1
    assert container.dao.summary()["sent_today"] == 0


def test_send_one_denied_without_approval(container, seeded, invocation_ctx):
    container.mail = FakeMail()
    result = send_one(container, seeded["draft_id"], dry_run=True)
    assert result["status"] == "denied"
    assert len(container.mail.calls) == 0
