"""Component: normalize and validate LLM-extracted contacts. No I/O."""

from ..models.entities import Contact
from ..models.values import EmailAddress

MAX_CONTACTS_PER_PAGE = 25


class ContactNormalizer:
    """Turns raw extraction JSON into validated Contact entities.

    Never invents data: emails are only kept when explicitly present and valid.
    """

    def normalize(
        self, data: dict, hospital_id: int | None = None, source_url: str = ""
    ) -> list[Contact]:
        contacts: list[Contact] = []
        for item in (data.get("contacts") or [])[:MAX_CONTACTS_PER_PAGE]:
            name = str(item.get("name") or "").strip()
            if not name:
                continue

            email_obj: EmailAddress | None = None
            raw_email = item.get("email")
            if raw_email:
                try:
                    email_obj = EmailAddress(value=str(raw_email))
                except ValueError:
                    email_obj = None

            try:
                confidence = float(item.get("confidence") or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0

            contacts.append(
                Contact(
                    hospital_id=hospital_id,
                    name=name,
                    title=self._clean(item.get("title")),
                    department=self._clean(item.get("department")),
                    email=email_obj,
                    source_url=source_url or None,
                    confidence=max(0.0, min(1.0, confidence)),
                )
            )
        return contacts

    @staticmethod
    def _clean(value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None
