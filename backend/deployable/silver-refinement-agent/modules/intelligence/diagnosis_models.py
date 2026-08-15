from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DiagnosisEvidence(BaseModel):
    source: str
    code: str
    detail: str
    weight: int = Field(ge=0, le=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class RootCauseCandidate(BaseModel):
    rank: int = Field(ge=1)
    reason: str
    confidence: float = Field(ge=0, le=1)
    evidence_codes: list[str] = Field(default_factory=list)


class DiagnosisSummary(BaseModel):
    category: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool


class DiagnosisTimelineItem(BaseModel):
    event_at: datetime | None = None
    event_type: str
    source: str
    detail: str


class IntelligenceExecutionDiagnosis(BaseModel):
    execution_id: str
    generated_at: datetime
    diagnosis: DiagnosisSummary
    summary: str
    root_causes: list[RootCauseCandidate] = Field(default_factory=list)
    evidence: list[DiagnosisEvidence] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    timeline: list[DiagnosisTimelineItem] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    context_completeness: str
