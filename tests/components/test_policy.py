from electivesmed.components.policy import PolicyGate
from electivesmed.models.entities import Contact
from electivesmed.models.enums import DraftStatus

from tests import constants as C


def test_pending_draft_is_denied(container, seeded, policy_gate):
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "approval" in decision.reason


def test_approved_draft_allowed_dry_run(container, approved, policy_gate):
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert decision.allowed
    assert any("opt-out" in warning for warning in decision.warnings)


def test_contact_without_email_is_denied(container, seeded, policy_gate):
    draft = container.dao.get_draft(seeded["draft_id"])

    decision = policy_gate.check_send(draft, Contact(name="No Email"), dry_run=True)
    assert not decision.allowed
    assert "no email" in decision.reason


def test_suppressed_email_is_denied(container, approved, policy_gate):
    container.dao.add_suppression(C.CONTACT_EMAIL, "unsubscribe")
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "suppression" in decision.reason


def test_daily_cap_blocks_real_send(container, approved, policy_gate):
    container.settings.limits.daily_send_cap = 0
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=False)
    assert not decision.allowed
    assert "cap" in decision.reason


def test_per_domain_cap_blocks_real_send(container, approved):
    class CountingDao:
        def __init__(self, dao):
            self._dao = dao

        def __getattr__(self, name):
            return getattr(self._dao, name)

        def sends_today(self):
            return 0

        def sends_today_for_domain(self, domain):
            return container.settings.limits.per_domain_cap

    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])
    gate = PolicyGate(CountingDao(container.dao), container.settings)

    decision = gate.check_send(draft, contact, dry_run=False)
    assert not decision.allowed
    assert "per-domain" in decision.reason


def test_spam_words_block(container, approved, policy_gate):
    draft = container.dao.get_draft(approved["draft_id"])
    draft.body_text = "This is a free guarantee, act now."
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "spam" in decision.reason


def test_style_violation_blocks_send(container, approved, policy_gate):
    draft = container.dao.get_draft(approved["draft_id"])
    draft.body_text = "We can leverage this to streamline your hiring."
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "AI-typical words" in decision.reason


def test_empty_subject_is_denied(container, approved, policy_gate):
    draft = container.dao.get_draft(approved["draft_id"])
    draft.subject = "   "
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "subject" in decision.reason


def test_check_content_accepts_clean_copy(policy_gate):
    decision = policy_gate.check_content("Short subject", C.CLEAN_BODY)
    assert decision.allowed


def test_save_draft_unknown_contact_is_denied(policy_gate):
    decision = policy_gate.check_save_draft(None, "Subject", C.DRAFT_BODY)
    assert not decision.allowed
    assert "unknown contact" in decision.reason


def test_save_draft_empty_fields_are_denied(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_save_draft(contact, " ", " ")
    assert not decision.allowed
    assert "must not be empty" in decision.reason


def test_save_draft_contact_without_email_is_denied(policy_gate):
    decision = policy_gate.check_save_draft(Contact(name="No Email"), "Subject", C.DRAFT_BODY)
    assert not decision.allowed
    assert "no email" in decision.reason


def test_save_draft_suppressed_contact_is_denied(container, seeded, policy_gate):
    container.dao.add_suppression(C.CONTACT_EMAIL, "unsubscribe")
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_save_draft(contact, "Subject", C.DRAFT_BODY)
    assert not decision.allowed
    assert "suppressed" in decision.reason


def test_save_draft_style_violation_is_denied(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_save_draft(contact, "Subject", "Hi \u2014 quick note.")
    assert not decision.allowed
    assert "em dash" in decision.reason


def test_save_draft_accepts_clean_copy(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_save_draft(contact, "Short subject", C.CLEAN_BODY)
    assert decision.allowed


def test_approved_draft_status_has_precedence_over_caps(container, approved, policy_gate):
    container.settings.limits.daily_send_cap = 0
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert decision.allowed


def test_draft_status_guards_are_ordered_before_content(container, seeded, policy_gate):
    draft = container.dao.get_draft(seeded["draft_id"])
    draft.subject = ""
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "approval" in decision.reason


def test_rejected_draft_is_denied(container, seeded, policy_gate):
    container.dao.set_draft_status(seeded["draft_id"], DraftStatus.REJECTED)
    draft = container.dao.get_draft(seeded["draft_id"])
    contact = container.dao.get_contact(seeded["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "rejected" in decision.reason


def test_long_body_adds_warning(container, approved, policy_gate):
    draft = container.dao.get_draft(approved["draft_id"])
    draft.body_text = " ".join(["professional note"] * 300)
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert decision.allowed
    assert any("unusually long" in warning for warning in decision.warnings)


def test_eu_without_lawful_basis_is_blocked(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "DE"

    decision = policy_gate.check_recipient_compliance(contact)
    assert not decision.allowed
    assert "lawful basis" in decision.reason


def test_eu_with_lawful_basis_is_allowed(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "DE"
    contact.lawful_basis = "legitimate_interest_b2b"

    assert policy_gate.check_recipient_compliance(contact).allowed


def test_eu_policy_warn_allows_with_warning(container, seeded, policy_gate):
    container.settings.compliance.eu_policy = "warn"
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "DE"

    decision = policy_gate.check_recipient_compliance(contact)
    assert decision.allowed
    assert any("lawful basis" in warning for warning in decision.warnings)


def test_us_requires_postal_address(container, seeded, policy_gate):
    container.settings.sender.postal_address = ""
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "US"

    decision = policy_gate.check_recipient_compliance(contact)
    assert not decision.allowed
    assert "postal address" in decision.reason


def test_us_with_postal_address_is_allowed(container, seeded, policy_gate):
    container.settings.sender.postal_address = "1 Main St, Fresno, CA"
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "US"

    assert policy_gate.check_recipient_compliance(contact).allowed


def test_us_policy_warn_allows_with_warning(container, seeded, policy_gate):
    container.settings.compliance.us_policy = "warn"
    container.settings.sender.postal_address = ""
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "US"

    decision = policy_gate.check_recipient_compliance(contact)
    assert decision.allowed
    assert any("postal address" in warning for warning in decision.warnings)


def test_jurisdiction_override_relaxes_rule(container, seeded, policy_gate):
    container.settings.compliance.jurisdiction_overrides = {
        "DE": {"requires_lawful_basis": False}
    }
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "DE"

    assert policy_gate.check_recipient_compliance(contact).allowed


def test_default_jurisdiction_is_allowed(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "TR"

    assert policy_gate.check_recipient_compliance(contact).allowed


def test_send_blocked_for_eu_without_basis(container, approved, policy_gate):
    contact = container.dao.get_contact(approved["contact_id"])
    contact.country = "FR"
    draft = container.dao.get_draft(approved["draft_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "lawful basis" in decision.reason


def test_save_draft_blocked_for_us_without_address(container, seeded, policy_gate):
    contact = container.dao.get_contact(seeded["contact_id"])
    contact.country = "US"
    container.settings.sender.postal_address = ""

    decision = policy_gate.check_save_draft(contact, "Subject", C.CLEAN_BODY)
    assert not decision.allowed
    assert "postal address" in decision.reason


# -------------------------------------------------------------- attachments


def _upload_and_attach(container, draft_id, cv_pdf):
    from electivesmed.services.attachments import add_attachment, attach_to_draft

    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    attach_to_draft(container, draft_id, attachment.id)
    return attachment


def test_send_denied_when_too_many_attachments(container, approved, policy_gate, cv_pdf):
    _upload_and_attach(container, approved["draft_id"], cv_pdf)
    container.settings.attachments.max_files = 0
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "per-email limit" in decision.reason


def test_send_denied_when_total_size_exceeded(container, approved, policy_gate, cv_pdf):
    _upload_and_attach(container, approved["draft_id"], cv_pdf)
    container.settings.attachments.max_total_mb = 0
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "MB limit" in decision.reason


def test_send_denied_when_attachment_type_not_allowed(container, approved, policy_gate):
    import hashlib

    from electivesmed.models.entities import Attachment

    payload = b"MZ fake executable"
    attachment = Attachment(
        filename="tool.exe",
        content_type="application/x-msdownload",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        data=payload,
    )
    attachment_id = container.dao.save_attachment(attachment)
    container.dao.attach_to_draft(approved["draft_id"], attachment_id)
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "not allowed" in decision.reason


def test_send_denied_when_attachment_too_large(container, approved, policy_gate, cv_pdf):
    _upload_and_attach(container, approved["draft_id"], cv_pdf)
    container.settings.attachments.max_file_mb = 0
    draft = container.dao.get_draft(approved["draft_id"])
    contact = container.dao.get_contact(approved["contact_id"])

    decision = policy_gate.check_send(draft, contact, dry_run=True)
    assert not decision.allowed
    assert "per-file size limit" in decision.reason


def test_attachments_check_skips_unsaved_draft(policy_gate):
    from electivesmed.models.entities import Draft

    draft = Draft(
        invocation_id=C.INVOCATION_ID,
        contact_id=1,
        subject="Unsaved",
        body_text=C.CLEAN_BODY,
    )

    assert policy_gate.check_attachments(draft).allowed
