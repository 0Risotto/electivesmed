"""Invoker: every agent run gets an invocation_id that is persisted for audit."""

from ..context import reset_invocation, set_invocation
from ..errors import LlmUnavailable
from ..models.enums import AgentName, InvocationStatus
from ..models.invocation import Invocation, InvocationContext, InvocationResult
from ..utils.ids import new_invocation_id


class Invoker:
    def __init__(self, container) -> None:
        self._container = container
        self._agents: dict[str, object] = {}

    def _agent(self, name: AgentName):
        if name.value not in self._agents:
            from ..builders.agents import build_outreach_agent, build_scout_agent

            if name == AgentName.SCOUT:
                self._agents[name.value] = build_scout_agent(self._container)
            else:
                self._agents[name.value] = build_outreach_agent(self._container)
        return self._agents[name.value]

    def invoke(
        self,
        agent_name: str | AgentName,
        prompt: str,
        campaign_id: int | None = None,
    ) -> InvocationResult:
        key = AgentName(str(agent_name))
        invocation_id = new_invocation_id()
        context = InvocationContext(
            invocation_id=invocation_id,
            agent_name=key.value,
            campaign_id=campaign_id,
        )
        dao = self._container.dao
        dao.record_invocation(
            Invocation(
                id=invocation_id,
                agent_name=key.value,
                campaign_id=campaign_id,
                status=InvocationStatus.RUNNING,
                input_json={"prompt": prompt},
            )
        )

        token = set_invocation(context)
        try:
            result = self._agent(key)(prompt)
            output = {"summary": str(result)}
            dao.finish_invocation(invocation_id, InvocationStatus.SUCCEEDED, output=output)
            return InvocationResult(
                invocation_id=invocation_id,
                status=InvocationStatus.SUCCEEDED,
                output=output,
            )
        except LlmUnavailable as exc:
            dao.finish_invocation(invocation_id, InvocationStatus.FAILED, error=str(exc))
            return InvocationResult(
                invocation_id=invocation_id,
                status=InvocationStatus.FAILED,
                error=str(exc),
            )
        except Exception as exc:  # agent failures must be auditable, not crash the CLI
            error = f"{type(exc).__name__}: {exc}"
            dao.finish_invocation(invocation_id, InvocationStatus.FAILED, error=error)
            return InvocationResult(
                invocation_id=invocation_id,
                status=InvocationStatus.FAILED,
                error=error,
            )
        finally:
            reset_invocation(token)
