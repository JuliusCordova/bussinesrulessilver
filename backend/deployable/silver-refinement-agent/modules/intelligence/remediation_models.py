from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RemediationAction(BaseModel):
    action_id: str
    title: str
    description: str
    owner_role: str
    priority: str
    action_type: str
    automation_level: str
    requires_approval: bool = True
    command_hint: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)


class RemediationPlan(BaseModel):
    execution_id: str
    generated_at: datetime
    category: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    strategy: str
    safe_to_automate: bool
    actions: list[RemediationAction] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
