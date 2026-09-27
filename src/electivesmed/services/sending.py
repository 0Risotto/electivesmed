"""Activity: send approved drafts via SMTP, policy-gated and throttled."""

import random
import time
from datetime import datetime, time as clock_time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..builders.payloads import build_payload
from ..constants import regions
from ..context import require_invocation
from ..models.entities import Send
from ..models.enums import DraftStatus, SendStatus
from .attachments import mail_attachments


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window_status(settings, contact) -> str | None:
    """None when the recipient's local time is inside the send window."""
    config = settings.sending
    if not config.window_enabled:
        return None
    tz_name = contact.timezone or regions.timezone_for(contact.country)
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo(regions.DEFAULT_TIMEZONE)

    local = _now().astimezone(zone)
    stamp = local.strftime("%a %H:%M")
    if local.weekday() not in config.window_days:
        return f"outside send window ({stamp} {zone.key})"
    try:
        start = clock_time.fromisoformat(config.window_start)
        end = clock_time.fromisoformat(config.window_end)
    except ValueError:
        return None
    if not start <= local.time() <= end:
        return f"outside send window ({stamp} {zone.key})"
    return None


def send_one(
    container, draft_id: int, dry_run: bool = True, force_window: bool = False
) -> dict:
    ctx = require_invocation()
    draft = container.dao.get_draft(draft_id)
    if draft is None:
        return {"status": "error", "error": f"draft {draft_id} not found"}
    contact = container.dao.get_contact(draft.contact_id)
    if contact is None:
        return {"status": "error", "error": f"contact {draft.contact_id} not found"}

    decision = container.policy.check_send(draft, contact, dry_run)
    if not decision.allowed:
        return {"status": "denied", "draft_id": draft_id, "reason": decision.reason}

    if not dry_run and not force_window:
        deferred_reason = _window_status(container.settings, contact)
        if deferred_reason:
            return {
                "status": "deferred",
                "draft_id": draft_id,
                "to": contact.email_value,
                "reason": deferred_reason,
            }

    settings = container.settings
    attachments = mail_attachments(container, draft.id or 0)
    payload = build_payload(
        draft,
        contact,
        from_email=settings.sender.email or settings.smtp.from_email,
        reply_to=settings.sender.reply_to or None,
        include_opt_out=settings.sending.include_opt_out,
        postal_address=settings.sender.postal_address,
        sender_name=settings.sender.name,
        organization=settings.sender.organization,
        attachments=attachments,
    )
    receipt = container.mail.send(payload, dry_run=dry_run)

    send = Send(
        invocation_id=ctx.invocation_id,
        draft_id=draft.id,
        contact_id=contact.id,
        message_id=receipt.message_id,
        to_email=payload.to,
        status=receipt.status,
        error=receipt.error,
    )
    send_id = container.dao.record_send(send)

    if not dry_run:
        if receipt.status == SendStatus.SENT:
            container.dao.set_draft_status(draft.id, DraftStatus.SENT)
            container.dao.record_sent_attachments(
                send_id, container.dao.find_draft_attachments(draft.id)
            )
        elif not receipt.accepted:
            container.dao.set_draft_status(draft.id, DraftStatus.SEND_FAILED)

    return {
        "send_id": send_id,
        "draft_id": draft.id,
        "to": payload.to,
        "status": str(receipt.status),
        "message_id": receipt.message_id,
        "error": receipt.error,
        "dry_run": dry_run,
        "attachments": [item.filename for item in attachments],
        "warnings": list(decision.warnings),
    }


def send_batch(
    container,
    draft_ids: list[int] | None = None,
    limit: int = 10,
    dry_run: bool = True,
    force_window: bool = False,
) -> dict:
    if draft_ids:
        ids = draft_ids[:limit]
    else:
        ids = [
            d.id
            for d in container.dao.find_drafts(DraftStatus.APPROVED, limit=limit)
            if d.id is not None
        ]
    if not ids:
        return {"status": "noop", "note": "no approved drafts found", "results": []}

    limits = container.settings.limits
    results: list[dict] = []
    for index, draft_id in enumerate(ids):
        if not dry_run and index > 0:
            time.sleep(random.uniform(limits.min_delay_seconds, limits.max_delay_seconds))
        results.append(send_one(container, draft_id, dry_run, force_window))

    sent = sum(1 for r in results if r.get("status") == SendStatus.SENT.value)
    dry = sum(1 for r in results if r.get("status") == SendStatus.DRY_RUN.value)
    denied = sum(1 for r in results if r.get("status") == "denied")
    failed = sum(1 for r in results if r.get("status") == SendStatus.FAILED.value)
    deferred = sum(1 for r in results if r.get("status") == "deferred")
    return {
        "status": "done",
        "attempted": len(results),
        "sent": sent,
        "dry_run": dry,
        "denied": denied,
        "failed": failed,
        "deferred": deferred,
        "results": results,
    }
