from electivesmed.models.enums import InvocationStatus
from electivesmed.models.invocation import Invocation

from tests import constants as C


def test_dashboard_renders_empty(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "No pending drafts" in response.text
    assert "No campaigns yet" in response.text


def test_dashboard_with_data(client, container, seeded, campaign_draft):
    container.dao.record_invocation(
        Invocation(
            id="inv_done",
            agent_name="scout",
            status=InvocationStatus.SUCCEEDED,
            input_json={},
            output_json={"summary": "scouted"},
        )
    )

    response = client.get("/")

    assert "inv_done" in response.text
    assert "scouted" in response.text
    assert C.DRAFT_SUBJECT in response.text
    assert C.CAMPAIGN_NAME in response.text


def test_invocation_status_polls_until_finished(client, container):
    container.dao.record_invocation(
        Invocation(
            id="inv_run",
            agent_name="scout",
            status=InvocationStatus.RUNNING,
            input_json={},
        )
    )

    running = client.get("/invocations/inv_run/status")
    assert 'hx-trigger="every 2s"' in running.text

    container.dao.finish_invocation(
        "inv_run", InvocationStatus.SUCCEEDED, output={"summary": "all good"}
    )
    done = client.get("/invocations/inv_run/status")

    assert "all good" in done.text
    assert "hx-trigger" not in done.text


def test_invocation_status_unknown_is_running(client):
    response = client.get("/invocations/missing/status")

    assert response.status_code == 200
    assert "running" in response.text
