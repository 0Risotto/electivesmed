from electivesmed.models.entities import Campaign, Draft
from electivesmed.models.enums import DraftStatus
from electivesmed.tools import build_action_tools, build_read_tools

from tests import constants as C
from tests.fakes import FakeLlm


def _tools_by_name(container) -> dict:
    return {tool.tool_name: tool for tool in build_read_tools(container)}


def _action_tools_by_name(container) -> dict:
    return {tool.tool_name: tool for tool in build_action_tools(container)}


def test_read_tool_names(container):
    assert set(_tools_by_name(container)) == C.READ_TOOLS


def test_action_tool_names(container):
    assert set(_action_tools_by_name(container)) == C.ACTION_TOOLS


def test_list_sources_tool(container):
    sources = _tools_by_name(container)["list_sources"]()

    assert sources[0]["name"] == "cms"


def test_fetch_source_tool(container, fake_fetch):
    result = _tools_by_name(container)["fetch_source"]("cms", 10)

    assert result["hospitals_added_or_updated"] == 2


def test_fetch_page_tools(container, staff_page_html):
    from tests.fakes import FakeFetch

    container.http = FakeFetch(data=staff_page_html)
    tools = _tools_by_name(container)

    assert "Our Staff" in tools["fetch_page"]("http://h.test/staff")
    assert "Our Staff" in tools["fetch_staff_page"]("Test Hospital", "http://h.test/staff")


def test_extract_contacts_tool(container, extraction_response):
    container.llm = FakeLlm(json_response=extraction_response)

    result = _tools_by_name(container)["extract_contacts"]("page text")

    assert result["extracted"] == 2


def test_score_contacts_tool(container, seeded):
    container.llm = FakeLlm(available=False)

    result = _tools_by_name(container)["score_contacts"]()

    assert result["scored"] == 1


def test_lookup_tools(container, seeded):
    tools = _tools_by_name(container)

    unknown = tools["lookup_contacts"]("bogus")
    assert "error" in unknown[0]

    contacts = tools["lookup_contacts"]()
    assert contacts[0]["email"] == C.CONTACT_EMAIL


def test_check_suppression_tool(container):
    tools = _tools_by_name(container)

    assert tools["check_suppression"](C.CONTACT_EMAIL)["suppressed"] is False
    container.dao.add_suppression(C.CONTACT_EMAIL, "unsubscribe")
    assert tools["check_suppression"](C.CONTACT_EMAIL)["suppressed"] is True


def test_get_campaign_tool(container):
    tools = _tools_by_name(container)

    assert "error" in tools["get_campaign"]("missing")
    container.dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL))
    assert tools["get_campaign"](C.CAMPAIGN_NAME)["goal"] == C.CAMPAIGN_GOAL


def test_save_draft_action_tool(container, seeded, invocation_ctx):
    tools = _action_tools_by_name(container)

    result = tools["save_draft"](
        contact_id=seeded["contact_id"],
        campaign_name=C.CAMPAIGN_NAME,
        subject="A short subject",
        body_text=C.CLEAN_BODY,
    )

    assert result["status"] == "pending_review"


def test_send_email_action_tool(container, approved, invocation_ctx, fake_mail):
    tools = _action_tools_by_name(container)

    result = tools["send_email"](draft_id=approved["draft_id"], dry_run=True)

    assert result["status"] == "dry_run"


def test_send_batch_action_tool(container, invocation_ctx, fake_mail):
    result = _action_tools_by_name(container)["send_batch"](dry_run=True)

    assert result["status"] == "noop"


def test_suppress_contact_action_tool(container):
    result = _action_tools_by_name(container)["suppress_contact"](C.CONTACT_EMAIL, "manual")

    assert result["status"] == "suppressed"


def test_save_draft_tool_attaches_defaults(container, seeded, invocation_ctx, cv_pdf):
    from electivesmed.services.attachments import add_attachment

    add_attachment(container, "cv.pdf", cv_pdf)
    container.settings.attachments.defaults = ["cv.pdf"]

    result = _action_tools_by_name(container)["save_draft"](
        contact_id=seeded["contact_id"],
        campaign_name=C.CAMPAIGN_NAME,
        subject="A short subject",
        body_text=C.CLEAN_BODY,
    )

    assert result["attachments"] == ["cv.pdf"]


def test_save_draft_tool_attaches_explicit_names(container, seeded, invocation_ctx, cv_pdf):
    from electivesmed.services.attachments import add_attachment

    add_attachment(container, "cv.pdf", cv_pdf)

    result = _action_tools_by_name(container)["save_draft"](
        contact_id=seeded["contact_id"],
        campaign_name=C.CAMPAIGN_NAME,
        subject="A short subject",
        body_text=C.CLEAN_BODY,
        attachments="cv.pdf, missing.pdf",
    )

    assert result["attachments"] == ["cv.pdf"]
