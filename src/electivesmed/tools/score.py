"""Thin tool over the scoring activity."""

from strands import tool

from ..services.scoring import score_contacts as score_contacts_activity


def build(container) -> list:
    @tool
    def score_contacts(contact_ids: list[int] | None = None, limit: int = 50) -> dict:
        """Score stored contacts against the sender's preferences and persist fit scores.

        Args:
            contact_ids: Optional explicit contact ids; defaults to most recent unscored contacts.
            limit: Maximum number of contacts to score when ids are not given.
        """
        return score_contacts_activity(container, contact_ids, limit)

    return [score_contacts]
