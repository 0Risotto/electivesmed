from electivesmed.converters.invocation import invocation_to_view
from electivesmed.models.enums import InvocationStatus
from electivesmed.models.invocation import Invocation

from tests import constants as C


def test_invocation_to_view_running():
    invocation = Invocation(
        id=C.INVOCATION_ID,
        agent_name="scout",
        status=InvocationStatus.RUNNING,
        input_json={"prompt": "find"},
    )

    view = invocation_to_view(invocation)

    assert view.id == C.INVOCATION_ID
    assert view.agent == "scout"
    assert view.status == "running"
    assert view.finished_at is None
    assert view.output is None


def test_invocation_to_view_finished_with_error():
    invocation = Invocation(
        id=C.INVOCATION_ID,
        agent_name="outreach",
        status=InvocationStatus.FAILED,
        input_json={},
        error="boom",
    )
    invocation.finished_at = invocation.started_at

    view = invocation_to_view(invocation)

    assert view.finished_at is not None
    assert view.error == "boom"
