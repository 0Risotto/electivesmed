from electivesmed.models.enums import InvocationStatus
from electivesmed.models.invocation import InvocationContext, InvocationResult

from tests import constants as C


def test_invocation_context_defaults():
    ctx = InvocationContext(invocation_id=C.INVOCATION_ID, agent_name="scout")

    assert ctx.campaign_id is None


def test_invocation_result_ok_property():
    ok = InvocationResult(invocation_id="inv", status=InvocationStatus.SUCCEEDED)
    failed = InvocationResult(invocation_id="inv", status=InvocationStatus.FAILED)

    assert ok.ok
    assert not failed.ok
    assert failed.output == {}
