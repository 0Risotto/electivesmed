"""Store summary → client DTO mapping."""

from ..models.views import SummaryView


def summary_to_view(summary: dict, daily_cap: int) -> SummaryView:
    sent_today = int(summary.get("sent_today", 0))
    return SummaryView(
        hospitals=summary.get("hospitals", 0),
        contacts=summary.get("contacts", 0),
        contacts_with_email=summary.get("contacts_with_email", 0),
        contacts_scored=summary.get("contacts_scored", 0),
        drafts_pending=summary.get("drafts_pending", 0),
        drafts_approved=summary.get("drafts_approved", 0),
        sent_today=sent_today,
        sent_total=summary.get("sent_total", 0),
        suppressed=summary.get("suppressed", 0),
        daily_cap=daily_cap,
        remaining_today=max(0, daily_cap - sent_today),
    )
