"""Component: policy gate. Every side-effectful action is checked here before it runs."""

from dataclasses import dataclass, field

from ..compliance import OPT_OUT_SENTENCE, SPAM_WORDS
from ..constants.limits import MAX_BODY_WORDS
from ..models.entities import Contact, Draft
from ..models.enums import DraftStatus
from ..utils.email import email_domain
from ..utils.text import word_count


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)


class PolicyGate:
    def __init__(self, dao, settings) -> None:
        self.dao = dao
        self.settings = settings

    def check_send(self, draft: Draft, contact: Contact, dry_run: bool) -> Decision:
        if contact.email is None:
            return Decision(False, "contact has no email address")
        if draft.status != DraftStatus.APPROVED:
            return Decision(
                False,
                f"draft {draft.id} status is {draft.status}; human approval is required first",
            )
        if self.dao.is_suppressed(contact.email.value):
            return Decision(False, f"{contact.email.value} is on the suppression list")

        if not dry_run:
            cap = self.settings.limits.daily_send_cap
            if self.dao.sends_today() >= cap:
                return Decision(False, f"daily send cap reached ({cap})")
            domain = email_domain(contact.email.value)
            domain_cap = self.settings.limits.per_domain_cap
            if self.dao.sends_today_for_domain(domain) >= domain_cap:
                return Decision(False, f"per-domain cap reached for {domain} ({domain_cap}/day)")

        warnings: list[str] = []
        body = draft.body_text
        if OPT_OUT_SENTENCE not in body:
            warnings.append("opt-out sentence missing; it will be appended at send time")
        lowered = body.lower()
        hits = [word for word in SPAM_WORDS if word in lowered]
        if hits:
            return Decision(False, f"spam trigger words present: {', '.join(hits)}")
        if word_count(body) > MAX_BODY_WORDS * 2:
            warnings.append("body is unusually long")
        if not draft.subject.strip():
            return Decision(False, "draft has an empty subject")

        return Decision(True, "ok", tuple(warnings))

    def check_save_draft(self, contact: Contact | None, subject: str, body: str) -> Decision:
        if contact is None:
            return Decision(False, "unknown contact")
        if not subject.strip() or not body.strip():
            return Decision(False, "subject and body must not be empty")
        if contact.email is None:
            return Decision(False, "contact has no email address; nothing to send")
        if self.dao.is_suppressed(contact.email.value):
            return Decision(False, f"{contact.email.value} is suppressed; do not draft")
        return Decision(True, "ok")
