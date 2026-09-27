"""Builder: render system/request prompts from profile, settings, and campaign data."""

from string import Template

from ..compliance import AI_TYPICAL_TERMS, OPT_OUT_SENTENCE
from ..models.config import Profile, Settings
from ..models.entities import Campaign
from ..prompts import (
    EXTRACTION_SYSTEM,
    OUTREACH_SYSTEM,
    SCORING_SYSTEM,
    SCOUT_SYSTEM,
)


def _join(items: list[str], fallback: str = "any") -> str:
    return ", ".join(items) if items else fallback


def _preferences(profile: Profile) -> dict:
    return {
        "specialties": _join(profile.specialties),
        "target_roles": _join(profile.target_roles),
        "locations": _join(profile.locations),
        "hospital_types": _join(profile.hospital_types),
        "must_haves": _join(profile.must_haves),
        "avoid": _join(profile.avoid, "nothing specified"),
    }


def scout_system(profile: Profile, settings: Settings) -> str:
    values = {
        "sender_name": settings.sender.name,
        "sender_role": settings.sender.role,
        "goal": profile.goal,
        **_preferences(profile),
    }
    return Template(SCOUT_SYSTEM).safe_substitute(values)


def outreach_system(
    profile: Profile, settings: Settings, campaign: Campaign | None = None
) -> str:
    sender = settings.sender
    sender_details = (
        f"name: {sender.name}; role: {sender.role}; organization: {sender.organization}; "
        f"email: {sender.email}; specialties: {_join(profile.specialties)}"
    )
    values = {
        "sender_name": sender.name,
        "sender_role": sender.role,
        "campaign_goal": (campaign.goal if campaign else profile.goal),
        "tone": (campaign.tone if campaign else profile.tone),
        "language": (campaign.language if campaign else profile.language),
        "max_words": "140",
        "ask": profile.ask,
        "opt_out_sentence": OPT_OUT_SENTENCE,
        "banned_terms": ", ".join(AI_TYPICAL_TERMS),
        "sender_details": sender_details,
    }
    return Template(OUTREACH_SYSTEM).safe_substitute(values)


def extraction_system() -> str:
    return EXTRACTION_SYSTEM


def scoring_system(profile: Profile) -> str:
    return Template(SCORING_SYSTEM).safe_substitute(_preferences(profile))


def default_scout_prompt(container, instructions: str = "") -> str:
    """Request prompt for a scout activity run."""
    profile = container.profile
    preferences = (
        f"specialties={profile.specialties}, target_roles={profile.target_roles}, "
        f"locations={profile.locations}, hospital_types={profile.hospital_types}, "
        f"must_haves={profile.must_haves}, avoid={profile.avoid}"
    )
    prompt = (
        "Scout hospitals, staff, and opportunities that match my preferences. "
        f"Preferences: {preferences}. Goal: {profile.goal}. "
        "If the database has few hospitals, start with list_sources and fetch_source('cms'). "
        "Then fetch public staff/leadership pages for the top matching hospitals, extract contacts, "
        "and score them. Finish with what you found and what you skipped."
    )
    if instructions:
        prompt += f" Extra instructions: {instructions}"
    return prompt


def generate_prompt(container, campaign: Campaign, contacts: list, instructions: str = "") -> str:
    """Request prompt for an outreach drafting run."""
    contact_ids = [c.id for c in contacts if c.id is not None]
    prompt = (
        f"Generate personalized first-contact drafts for campaign {campaign.name!r}.\n"
        f"Campaign goal: {campaign.goal}\n"
        f"Contact ids to process: {contact_ids}\n"
        "For each contact: read the record with lookup_contacts, then call save_draft with "
        f"campaign_name={campaign.name!r}, a subject, body_text, a one-sentence rationale, "
        "and a confidence score.\n"
        "Skip contacts whose role or location clearly conflicts with my preferences and say why.\n"
        "Draft only; do not send any email."
    )
    if instructions:
        prompt += f"\nExtra instructions: {instructions}"
    return prompt
