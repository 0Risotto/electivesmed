import pytest

from electivesmed.context import require_invocation
from electivesmed.errors import LlmUnavailable
from electivesmed.models.enums import AgentName, InvocationStatus

from tests import constants as C


class _EchoAgent:
    def __call__(self, prompt):
        return f"handled: {prompt}"


def test_invoke_success_records_invocation(container):
    seen: dict = {}

    class RecordingAgent:
        def __call__(self, prompt):
            seen["invocation_id"] = require_invocation().invocation_id
            return "scout finished"

    container.invoker._agents[AgentName.SCOUT.value] = RecordingAgent()
    result = container.invoker.invoke(AgentName.SCOUT, "find hospitals")

    assert result.ok
    assert seen["invocation_id"] == result.invocation_id
    stored = container.dao.get_invocation(result.invocation_id)
    assert stored.status is InvocationStatus.SUCCEEDED
    assert stored.output_json["summary"] == "scout finished"
    assert stored.input_json["prompt"] == "find hospitals"


def test_invoke_accepts_string_agent_name(container):
    container.invoker._agents[AgentName.SCOUT.value] = _EchoAgent()
    result = container.invoker.invoke("scout", "hello")

    assert result.ok


def test_invoke_records_failure(container):
    class BrokenAgent:
        def __call__(self, prompt):
            raise RuntimeError("boom")

    container.invoker._agents[AgentName.SCOUT.value] = BrokenAgent()
    result = container.invoker.invoke(AgentName.SCOUT, "find hospitals")

    assert not result.ok
    assert "boom" in result.error
    assert container.dao.get_invocation(result.invocation_id).status is InvocationStatus.FAILED


def test_invoke_records_llm_unavailable(container):
    class UnavailableAgent:
        def __call__(self, prompt):
            raise LlmUnavailable("no key configured")

    container.invoker._agents[AgentName.SCOUT.value] = UnavailableAgent()
    result = container.invoker.invoke(AgentName.SCOUT, "find hospitals")

    assert not result.ok
    assert "no key" in result.error
    assert container.dao.get_invocation(result.invocation_id).status is InvocationStatus.FAILED


def test_unknown_agent_name_raises(container):
    with pytest.raises(ValueError):
        container.invoker.invoke("not-an-agent", "hello")


def test_agent_builder_is_used_and_cached(container, monkeypatch):
    import electivesmed.builders.agents as builders

    builds: list = []

    def fake_builder(_container):
        builds.append(1)
        return _EchoAgent()

    monkeypatch.setattr(builders, "build_scout_agent", fake_builder)
    first = container.invoker.invoke(AgentName.SCOUT, "one")
    second = container.invoker.invoke(AgentName.SCOUT, "two")

    assert first.ok and second.ok
    assert len(builds) == 1


def test_outreach_agent_builder_is_used(container, monkeypatch):
    import electivesmed.builders.agents as builders

    monkeypatch.setattr(builders, "build_outreach_agent", lambda _container: _EchoAgent())
    result = container.invoker.invoke(AgentName.OUTREACH, "draft emails", campaign_id=42)

    stored = container.dao.get_invocation(result.invocation_id)
    assert stored.agent_name == AgentName.OUTREACH.value
    assert stored.campaign_id == 42
