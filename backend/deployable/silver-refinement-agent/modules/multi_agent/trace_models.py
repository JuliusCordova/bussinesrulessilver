from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import OrchestratorResponse


class ReasoningTraceStage(BaseModel):
    stage_id: str
    sequence: int = Field(ge=1)
    stage_type: Literal[
        "REQUEST",
        "MEMORY_RETRIEVAL",
        "PLANNING",
        "SPECIALIST_EXECUTION",
        "MEMORY_GROUNDING",
        "CRITICAL_VALIDATION",
        "ADAPTIVE_REPLANNING",
        "HUMAN_REVIEW_GATE",
        "PERSISTENCE",
        "FINAL_RESPONSE",
    ]
    actor: str
    status: Literal[
        "COMPLETED",
        "SKIPPED",
        "BLOCKED",
        "REQUIRES_REVIEW",
    ]
    summary: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    decision: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUsageTrace(BaseModel):
    memory_id: str
    action: Literal["RETRIEVED", "INJECTED", "APPLIED", "BLOCKED"]
    memory_type: str
    agent_id: str | None = None
    source_agent_id: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    reason: str = ""
    evidence_precedence: str | None = None


class DecisionGateTrace(BaseModel):
    gate_id: str
    gate_type: Literal[
        "EVIDENCE_PRECEDENCE",
        "CRITICAL_VALIDATION",
        "ADAPTIVE_REPLANNING",
        "HUMAN_REVIEW",
    ]
    decision: str
    status: Literal["PASSED", "BLOCKED", "REQUIRES_REVIEW", "NOT_APPLICABLE"]
    finding_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ReasoningTrace(BaseModel):
    trace_id: str
    correlation_id: str
    schema_version: str = "1.0.0"
    session_id: str
    execution_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    question_fingerprint: str
    stages: list[ReasoningTraceStage] = Field(default_factory=list)
    agent_path: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    memory_usage: list[MemoryUsageTrace] = Field(default_factory=list)
    decision_gates: list[DecisionGateTrace] = Field(default_factory=list)
    conclusion_status: Literal["VALIDATED", "CONDITIONED", "REJECTED"]
    requires_human_review: bool
    final_provenance: dict[str, Any] = Field(default_factory=dict)
    redaction_applied: bool = True
    private_chain_of_thought_stored: bool = False
    persistence_status: Literal["NOT_REQUESTED", "PERSISTED", "FAILED"] = (
        "NOT_REQUESTED"
    )
    reasoning_trace_memory_id: str | None = None


class TraceableOrchestratorResponse(OrchestratorResponse):
    reasoning_trace_used: bool = True
    trace_id: str
    reasoning_trace: ReasoningTrace
    reasoning_trace_memory_id: str | None = None


class ReasoningTraceRecord(BaseModel):
    memory_id: str
    created_at: datetime
    trace: ReasoningTrace
