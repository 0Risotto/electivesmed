from electivesmed.builders.agents import (
    build_model,
    build_outreach_agent,
    build_scout_agent,
)
from electivesmed.models.enums import AgentName

from tests.constants import ACTION_TOOLS, READ_TOOLS


def test_build_model_passes_credentials(keyed_container):
    model = build_model(keyed_container)

    assert model.client_args["api_key"] == "sk-dummy"
    assert model.client_args["api_base"] == keyed_container.llm.base_url


def test_build_model_without_key_uses_empty_client_args(container):
    container.llm.api_key = ""
    model = build_model(container)

    assert model.client_args == {}


def test_build_scout_agent_has_read_tools_only(keyed_container):
    agent = build_scout_agent(keyed_container)

    assert agent.name == AgentName.SCOUT.value
    assert set(agent.tool_names) == READ_TOOLS


def test_build_outreach_agent_has_read_and_action_tools(keyed_container):
    agent = build_outreach_agent(keyed_container)

    assert agent.name == AgentName.OUTREACH.value
    assert set(agent.tool_names) == READ_TOOLS | ACTION_TOOLS
