"""Builder: construct Strands agents wired to DeepSeek and the tool surface."""

from strands import Agent
from strands.models.litellm import LiteLLMModel

from ..constants.limits import LLM_MAX_TOKENS
from ..models.enums import AgentName
from ..tools import build_action_tools, build_read_tools
from . import prompts


def build_model(container) -> LiteLLMModel:
    client_args: dict = {}
    if container.llm.api_key:
        client_args = {
            "api_key": container.llm.api_key,
            "api_base": container.llm.base_url,
        }
    return LiteLLMModel(
        client_args=client_args,
        model_id=container.settings.model.chat,
        params={
            "temperature": container.settings.model.temperature,
            "max_tokens": LLM_MAX_TOKENS,
        },
        stream=False,
    )


def build_scout_agent(container) -> Agent:
    return Agent(
        model=build_model(container),
        tools=build_read_tools(container),
        system_prompt=prompts.scout_system(container.profile, container.settings),
        name=AgentName.SCOUT.value,
        description="Finds hospitals, staff, and opportunities matching the sender's preferences.",
    )


def build_outreach_agent(container) -> Agent:
    return Agent(
        model=build_model(container),
        tools=[*build_read_tools(container), *build_action_tools(container)],
        system_prompt=prompts.outreach_system(container.profile, container.settings),
        name=AgentName.OUTREACH.value,
        description="Drafts personalized hospital outreach emails for human approval.",
    )
