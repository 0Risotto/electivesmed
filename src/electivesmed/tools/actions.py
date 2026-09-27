"""Thin tool wrappers for side-effectful actions (policy-gated downstream)."""

from strands import tool

from ..actions.drafts import save_draft as save_draft_action
from ..actions.suppression import suppress as suppress_action
from ..services.attachments import attach_by_names, attach_defaults
from ..services.sending import send_batch as send_batch_activity
from ..services.sending import send_one as send_one_activity


def build(container) -> list:
    @tool
    def save_draft(
        contact_id: int,
        campaign_name: str,
        subject: str,
        body_text: str,
        body_html: str = "",
        rationale: str = "",
        confidence: float = 0.0,
        attachments: str = "",
    ) -> dict:
        """Save a personalized outreach email as a PENDING draft for human review.

        The draft is never sent automatically; a human must approve it first.
        attachments: optional comma-separated document names from the library;
        defaults from settings are attached when left empty.
        """
        result = save_draft_action(
            container,
            contact_id,
            campaign_name,
            subject,
            body_text,
            body_html,
            rationale,
            confidence,
        )
        if result.get("status") == "pending_review":
            names = [name.strip() for name in attachments.split(",") if name.strip()]
            if names:
                result["attachments"] = attach_by_names(container, result["draft_id"], names)
            else:
                result["attachments"] = attach_defaults(container, result["draft_id"])
        return result

    @tool
    def send_email(draft_id: int, dry_run: bool = True, force_window: bool = False) -> dict:
        """Send an approved draft via SMTP, or simulate it with dry_run=True.

        Policy-gated: requires an APPROVED draft, checks the suppression list, jurisdiction
        rules, and daily/per-domain caps. Respects the recipient's local send window unless
        force_window is True. Defaults to dry-run.
        """
        return send_one_activity(container, draft_id, dry_run, force_window)

    @tool
    def send_batch(
        draft_ids: list[int] | None = None,
        limit: int = 10,
        dry_run: bool = True,
        force_window: bool = False,
    ) -> dict:
        """Send multiple approved drafts in one run, throttled between sends.

        Each send is individually policy-checked and respects the recipient send window
        unless force_window is True. Defaults to the approved queue and dry-run.
        """
        return send_batch_activity(container, draft_ids, limit, dry_run, force_window)

    @tool
    def suppress_contact(email: str, reason: str = "manual") -> dict:
        """Add an email address to the do-not-contact suppression list.

        Suppressed addresses are blocked by the policy gate for all future sends.
        """
        return suppress_action(container, email, reason)

    return [save_draft, send_email, send_batch, suppress_contact]
