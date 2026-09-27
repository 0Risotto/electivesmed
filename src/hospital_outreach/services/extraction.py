"""Activity: extract contacts from public page text and persist them."""

from ..builders.prompts import extraction_system
from ..components.extraction import ContactNormalizer
from ..converters.contact import contact_to_view


def extract_contacts(
    container,
    raw_text: str,
    source_url: str = "",
    hospital_id: int | None = None,
    hospital_name: str = "",
) -> dict:
    if not container.llm.available:
        return {"error": "DEEPSEEK_API_KEY is not set; extraction needs the LLM accessor"}
    user_prompt = (
        f"Hospital hint: {hospital_name or 'unknown'}\n"
        f"Source: {source_url or 'unknown'}\n\n"
        f"PAGE TEXT:\n{raw_text}"
    )
    data = container.llm.chat_json(extraction_system(), user_prompt)

    normalizer = ContactNormalizer()
    contacts = normalizer.normalize(data, hospital_id=hospital_id, source_url=source_url)
    ids = container.dao.save_contacts(contacts)
    return {
        "hospital_name": data.get("hospital_name") or hospital_name or None,
        "extracted": len(contacts),
        "saved_ids": ids,
        "contacts": [contact_to_view(c).model_dump(mode="json") for c in contacts],
    }
