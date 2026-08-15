from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GovernanceDecisionSummary(BaseModel):
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)


class GovernanceEnvironmentSummary(BaseModel):
    dev: int = Field(ge=0)
    qa: int = Field(ge=0)
    prod: int = Field(ge=0)


class GovernanceActivitySummary(BaseModel):
    promotions: int = Field(ge=0)
    rollbacks: int = Field(ge=0)
    audit_events: int = Field(ge=0)


class GovernanceSummaryResponse(BaseModel):
    generated_at: datetime
    total_current_packages: int = Field(ge=0)
    decisions: GovernanceDecisionSummary
    environments: GovernanceEnvironmentSummary
    activity: GovernanceActivitySummary
    compliance_status: str
