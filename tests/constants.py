"""Shared constants for the test suite."""

from electivesmed.compliance import OPT_OUT_SENTENCE

HOSPITAL_NAME = "Test Hospital"
HOSPITAL_CITY = "Fresno"
HOSPITAL_STATE = "CA"

CONTACT_NAME = "Jane Doe"
CONTACT_TITLE = "Chief Medical Officer"
CONTACT_EMAIL = "jane.doe@testhospital.org"
CONTACT_EMAIL_ALT = "john.smith@otherhospital.org"

DRAFT_SUBJECT = "Hello from a colleague"
DRAFT_BODY = "Hi Jane, this is a short professional note."
CLEAN_BODY = (
    "Hi Dr. Doe, I am a cardiologist in Fresno. "
    "Would you be open to a short call next week?"
)
OPT_OUT = OPT_OUT_SENTENCE

INVOCATION_ID = "inv_test"
CAMPAIGN_NAME = "test-campaign"
CAMPAIGN_GOAL = "Find cardiology opportunities."

SENDER_EMAIL = "me@example.org"
REPLY_TO = "reply@example.org"

READ_TOOLS = {
    "list_sources",
    "fetch_source",
    "fetch_page",
    "fetch_staff_page",
    "extract_contacts",
    "score_contacts",
    "lookup_contacts",
    "check_suppression",
    "get_campaign",
}
ACTION_TOOLS = {"save_draft", "send_email", "send_batch", "suppress_contact"}

# Sample datasets live in data/samples/ and are loaded by fixtures in conftest.py:
# hospitals_cms.csv, contacts.csv, extraction_response.json, staff_page.html
