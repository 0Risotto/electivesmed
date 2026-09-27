"""Read-only lookups over stored data."""

from strands import tool

from ..converters.contact import contact_to_view
from ..models.enums import ContactStatus


def build(container) -> list:
    @tool
    def lookup_contacts(status: str = "", limit: int = 25, scored_only: bool = False) -> list[dict]:
        """Look up stored contacts, best fit first.

        Args:
            status: Optional status filter (new, enriched, scored, skipped, suppressed).
            limit: Maximum rows to return.
            scored_only: Only return contacts that have a fit score.
        """
        parsed: ContactStatus | None = None
        if status:
            try:
                parsed = ContactStatus(status.strip().lower())
            except ValueError:
                return [{"error": f"unknown status {status!r}"}]
        contacts = container.dao.find_contacts(
            status=parsed, with_email_only=False, scored_only=scored_only, limit=limit
        )
        return [contact_to_view(c).model_dump(mode="json") for c in contacts]

    @tool
    def check_suppression(email: str) -> dict:
        """Check whether an email address is on the do-not-contact suppression list."""
        return {"email": email.strip().lower(), "suppressed": container.dao.is_suppressed(email)}

    @tool
    def get_campaign(name: str) -> dict:
        """Fetch a campaign by name, or return an error if it does not exist."""
        campaign = container.dao.get_campaign(name)
        if campaign is None:
            return {"error": f"campaign {name!r} not found"}
        return campaign.model_dump(mode="json")

    return [lookup_contacts, check_suppression, get_campaign]
