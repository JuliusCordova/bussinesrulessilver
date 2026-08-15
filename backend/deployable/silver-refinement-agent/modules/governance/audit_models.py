from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class GovernanceAuditEvent(BaseModel):
    event_id: str
    artifact_id: str
    event_type: str
    actor: str
    event_at: datetime
    source_environment: str | None = None
    target_environment: str | None = None
    decision: str | None = None
    comment: str | None = None
    immutable: bool = True


class GovernanceAuditTrailResponse(BaseModel):
    artifact_id: str
    total: int = Field(ge=0)
    events: list[GovernanceAuditEvent]
