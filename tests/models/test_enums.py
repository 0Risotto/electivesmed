from electivesmed.models.enums import (
    AgentName,
    ContactStatus,
    DraftStatus,
    InvocationStatus,
    SendStatus,
    SourceType,
)


def test_enums_render_as_plain_strings():
    assert str(ContactStatus.NEW) == "new"
    assert str(DraftStatus.PENDING) == "pending"
    assert str(SendStatus.DRY_RUN) == "dry_run"
    assert str(InvocationStatus.SUCCEEDED) == "succeeded"
    assert str(SourceType.CMS_DATASET) == "cms_dataset"
    assert str(AgentName.SCOUT) == "scout"


def test_enums_compare_to_strings():
    assert ContactStatus.SCORED == "scored"
    assert DraftStatus.APPROVED == "approved"
