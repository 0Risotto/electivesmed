"""Builder: MailPayload construction from drafts and contacts."""

from ..compliance import OPT_OUT_SENTENCE
from ..models.entities import Contact, Draft, MailPayload


def build_payload(
    draft: Draft,
    contact: Contact,
    from_email: str,
    reply_to: str | None = None,
    include_opt_out: bool = True,
) -> MailPayload:
    body = draft.body_text.strip()
    if include_opt_out and OPT_OUT_SENTENCE not in body:
        body = f"{body}\n\n{OPT_OUT_SENTENCE}"

    headers: dict[str, str] = {}
    if reply_to:
        headers["List-Unsubscribe"] = f"<mailto:{reply_to}?subject=unsubscribe>"

    return MailPayload(
        to=contact.email_value or "",
        from_email=from_email,
        reply_to=reply_to,
        subject=draft.subject,
        body_text=body,
        body_html=draft.body_html,
        headers=headers,
    )
