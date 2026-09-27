from electivesmed.clients.cli import views
from electivesmed.models.enums import InvocationStatus
from electivesmed.models.invocation import InvocationResult
from electivesmed.models.views import (
    ContactView,
    DraftPreview,
    InvocationView,
    SummaryView,
)

from tests import constants as C


def _contact_view(**overrides) -> ContactView:
    base = dict(
        id=1,
        hospital=C.HOSPITAL_NAME,
        name=C.CONTACT_NAME,
        title=C.CONTACT_TITLE,
        department="Cardiology",
        email=C.CONTACT_EMAIL,
        fit_score=0.9,
        fit_percent=90,
        status="scored",
        source_url=None,
    )
    base.update(overrides)
    return ContactView(**base)


def _draft_preview(**overrides) -> DraftPreview:
    base = dict(
        id=1,
        to_name=C.CONTACT_NAME,
        to_email=C.CONTACT_EMAIL,
        hospital=C.HOSPITAL_NAME,
        subject=C.DRAFT_SUBJECT,
        body_text=C.DRAFT_BODY,
        rationale="Matched role and location",
        confidence=0.8,
        status="pending",
        invocation_id=C.INVOCATION_ID,
    )
    base.update(overrides)
    return DraftPreview(**base)


def test_print_contacts(capsys):
    views.print_contacts([_contact_view()])

    assert C.CONTACT_NAME in capsys.readouterr().out


def test_print_contacts_handles_missing_fields(capsys):
    views.print_contacts([_contact_view(name=None, title=None, hospital=None, email=None, fit_percent=None)])

    assert "-" in capsys.readouterr().out


def test_print_drafts_table(capsys):
    views.print_drafts_table([_draft_preview()])

    assert C.DRAFT_SUBJECT[:20] in capsys.readouterr().out


def test_print_draft_full_with_rationale(capsys):
    views.print_draft_full(_draft_preview())

    output = capsys.readouterr().out
    assert "Rationale" in output
    assert C.CONTACT_EMAIL in output


def test_print_draft_full_without_rationale(capsys):
    views.print_draft_full(_draft_preview(rationale=None))

    assert "Rationale" not in capsys.readouterr().out


def test_print_invocation_result_success(capsys):
    result = InvocationResult(
        invocation_id="inv_ok",
        status=InvocationStatus.SUCCEEDED,
        output={"summary": "all good"},
    )

    views.print_invocation_result(result)

    output = capsys.readouterr().out
    assert "succeeded" in output
    assert "all good" in output


def test_print_invocation_result_failure(capsys):
    result = InvocationResult(
        invocation_id="inv_bad",
        status=InvocationStatus.FAILED,
        error="boom",
    )

    views.print_invocation_result(result)

    assert "boom" in capsys.readouterr().out


def test_print_invocations(capsys):
    row = InvocationView(
        id="inv_cli",
        agent="scout",
        status="succeeded",
        campaign_id=None,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at=None,
        error=None,
        output=None,
    )

    views.print_invocations([row])

    assert "inv_cli" in capsys.readouterr().out


def test_print_send_results(capsys):
    result = {
        "attempted": 1,
        "sent": 1,
        "dry_run": 0,
        "denied": 0,
        "failed": 0,
        "results": [{"draft_id": 7, "status": "sent", "to": C.CONTACT_EMAIL}],
    }

    views.print_send_results(result)

    output = capsys.readouterr().out
    assert "attempted=1" in output
    assert "draft 7" in output


def test_print_summary(capsys):
    view = SummaryView(
        hospitals=2,
        contacts=3,
        contacts_with_email=2,
        contacts_scored=1,
        drafts_pending=1,
        drafts_approved=1,
        sent_today=0,
        sent_total=4,
        suppressed=1,
        daily_cap=50,
        remaining_today=50,
    )

    views.print_summary(view)

    output = capsys.readouterr().out
    assert "hospitals" in output
    assert "remaining 50" in output


def test_print_json(capsys):
    views.print_json({"a": 1})

    assert '"a": 1' in capsys.readouterr().out
