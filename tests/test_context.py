import pytest

from electivesmed.context import (
    current_invocation,
    require_invocation,
    reset_invocation,
    set_invocation,
)
from electivesmed.models.invocation import InvocationContext


def test_default_context_is_none():
    assert current_invocation() is None


def test_set_and_reset_context():
    ctx = InvocationContext(invocation_id="inv_ctx", agent_name="test")
    token = set_invocation(ctx)

    assert current_invocation() is ctx

    reset_invocation(token)
    assert current_invocation() is None


def test_require_invocation_raises_without_context():
    with pytest.raises(RuntimeError, match="invocation"):
        require_invocation()


def test_require_invocation_returns_context():
    ctx = InvocationContext(invocation_id="inv_ctx", agent_name="test")
    token = set_invocation(ctx)
    try:
        assert require_invocation() is ctx
    finally:
        reset_invocation(token)
