"""Invocation tracking: one invocation per agent run."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..utils.time import utcnow
from .enums import InvocationStatus


class InvocationContext(BaseModel):
    invocation_id: str
    agent_name: str
    campaign_id: int | None = None


class Invocation(BaseModel):
    id: str
    agent_name: str
    campaign_id: int | None = None
    status: InvocationStatus
    input_json: dict = Field(default_factory=dict)
    output_json: dict | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class InvocationResult(BaseModel):
    invocation_id: str
    status: InvocationStatus
    output: dict = Field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == InvocationStatus.SUCCEEDED
