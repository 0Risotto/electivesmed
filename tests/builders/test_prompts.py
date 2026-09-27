from electivesmed.builders.prompts import (
    default_scout_prompt,
    extraction_system,
    generate_prompt,
    outreach_system,
    scoring_system,
    scout_system,
)
from electivesmed.models.config import Profile, Settings
from electivesmed.models.entities import Campaign, Contact

from tests import constants as C


def _profile() -> Profile:
    return Profile(
        goal=C.CAMPAIGN_GOAL,
        target_roles=[C.CONTACT_TITLE],
        specialties=["Cardiology"],
        locations=[C.HOSPITAL_CITY],
    )


def _campaign() -> Campaign:
    return Campaign(name=C.CAMPAIGN_NAME, goal="Hire cardiologists", tone="direct", language="en")


def test_scout_system_includes_preferences_and_goal():
    text = scout_system(_profile(), Settings())

    assert C.CAMPAIGN_GOAL in text
    assert C.CONTACT_TITLE in text
    assert C.HOSPITAL_CITY in text


def test_outreach_system_uses_profile_when_no_campaign():
    text = outreach_system(_profile(), Settings())

    assert C.CAMPAIGN_GOAL in text


def test_outreach_system_uses_campaign_overrides():
    text = outreach_system(_profile(), Settings(), _campaign())

    assert "Hire cardiologists" in text
    assert "direct" in text
    assert C.OPT_OUT in text
    assert "delve" in text


def test_extraction_system_is_static():
    assert "JSON" in extraction_system()


def test_scoring_system_substitutes_preferences():
    text = scoring_system(_profile())

    assert "Cardiology" in text
    assert C.CONTACT_TITLE in text


def test_default_scout_prompt_mentions_goal(container):
    prompt = default_scout_prompt(container)

    assert container.profile.goal in prompt
    assert "fetch_source('cms')" in prompt


def test_default_scout_prompt_appends_instructions(container):
    prompt = default_scout_prompt(container, "Only teaching hospitals")

    assert prompt.endswith("Extra instructions: Only teaching hospitals")


def test_generate_prompt_lists_contact_ids(container):
    contacts = [Contact(name="A"), Contact(name="B")]
    contacts[0].id = 1
    contacts[1].id = 2

    prompt = generate_prompt(container, _campaign(), contacts)

    assert "[1, 2]" in prompt
    assert C.CAMPAIGN_NAME in prompt


def test_generate_prompt_appends_instructions(container):
    prompt = generate_prompt(container, _campaign(), [], "Keep it under 100 words")

    assert "Extra instructions: Keep it under 100 words" in prompt
