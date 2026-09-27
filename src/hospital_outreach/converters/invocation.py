"""Invocation domain → client DTO mapping."""

from ..models.invocation import Invocation
from ..models.views import InvocationView


def invocation_to_view(invocation: Invocation) -> InvocationView:
    return InvocationView(
        id=invocation.id,
        agent=invocation.agent_name,
        status=str(invocation.status),
        campaign_id=invocation.campaign_id,
        started_at=invocation.started_at.isoformat(),
        finished_at=invocation.finished_at.isoformat() if invocation.finished_at else None,
        error=invocation.error,
        output=invocation.output_json,
    )
