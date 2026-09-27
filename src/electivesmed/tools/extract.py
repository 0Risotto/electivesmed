"""Thin tool over the extraction activity."""

from strands import tool

from ..services.extraction import extract_contacts as extract_contacts_activity


def build(container) -> list:
    @tool
    def extract_contacts(
        raw_text: str,
        source_url: str = "",
        hospital_id: int | None = None,
        hospital_name: str = "",
    ) -> dict:
        """Extract structured contact records from raw public page text and persist them.

        Never invents emails: only addresses explicitly present in the text are stored.
        Returns counts plus the extracted records.
        """
        return extract_contacts_activity(
            container, raw_text, source_url, hospital_id, hospital_name
        )

    return [extract_contacts]
