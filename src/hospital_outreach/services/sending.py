"""Activity: send approved drafts via SMTP, policy-gated and throttled."""

import random
import time

from ..builders.payloads import build_payload
from ..context import require_invocation
from ..models.entities import Send
from ..models.enums import DraftStatus, SendStatus


def send_one(container, draft_id: int, dry_run: bool = True) -> dict:
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

    settings = container.settings
    payload = build_payload(
        draft,
        contact,
        from_email=settings.sender.email or settings.smtp.from_email,
        reply_to=settings.sender.reply_to or None,
        include_opt_out=settings.sending.include_opt_out,
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
        "warnings": list(decision.warnings),
    }


def send_batch(
    container,
    draft_ids: list[int] | None = None,
    limit: int = 10,
    dry_run: bool = True,
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
        results.append(send_one(container, draft_id, dry_run))

    sent = sum(1 for r in results if r.get("status") == SendStatus.SENT.value)
    dry = sum(1 for r in results if r.get("status") == SendStatus.DRY_RUN.value)
    denied = sum(1 for r in results if r.get("status") == "denied")
    failed = sum(1 for r in results if r.get("status") == SendStatus.FAILED.value)
    return {
        "status": "done",
        "attempted": len(results),
        "sent": sent,
        "dry_run": dry,
        "denied": denied,
        "failed": failed,
        "results": results,
    }
