from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolDescriptor(BaseModel):
    tool_id: str
    name: str
    domain: str
    description: str
    agent_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True
    version: str = "1.0.0"


class AgentDescriptor(BaseModel):
    agent_id: str
    name: str
    domain: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    enabled: bool = True
    version: str = "1.0.0"
    execution_phase: Literal["SPECIALIST", "VALIDATOR"] = "SPECIALIST"


class AgentSelection(BaseModel):
    agent_id: str
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)


class OrchestrationPlan(BaseModel):
    strategy: str
    selections: list[AgentSelection] = Field(default_factory=list)
    fallback_used: bool = False


class InjectedMemory(BaseModel):
    memory_id: str
    memory_type: str
    source_agent_id: str | None = None
    score: float = Field(ge=0, le=1)
    match_type: str
    excerpt: str
    injection_reason: str


class AgentMemoryContext(BaseModel):
    agent_id: str
    mode: Literal["STRICT", "COLLABORATIVE"] = "STRICT"
    candidate_count: int = Field(default=0, ge=0)
    injected_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    total_chars: int = Field(default=0, ge=0)
    max_items: int = Field(default=3, ge=1)
    max_chars: int = Field(default=1800, ge=100)
    truncated: bool = False
    memories: list[InjectedMemory] = Field(default_factory=list)


class GroundedMemoryDecision(BaseModel):
    memory_id: str
    memory_type: str
    source_agent_id: str | None = None
    score: float = Field(ge=0, le=1)
    status: Literal["APPLIED", "BLOCKED"]
    reason: str
    contribution: str | None = None


class AgentMemoryGrounding(BaseModel):
    agent_id: str
    enabled: bool = True
    evidence_precedence: Literal["CURRENT_EVIDENCE_WINS"] = "CURRENT_EVIDENCE_WINS"
    candidate_count: int = Field(default=0, ge=0)
    applied_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    max_items: int = Field(default=2, ge=1, le=10)
    historical_context: list[str] = Field(default_factory=list)
    decisions: list[GroundedMemoryDecision] = Field(default_factory=list)


class AgentTaskResult(BaseModel):
    agent_id: str
    status: str
    summary: str
    tools_used: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    memory_context: AgentMemoryContext | None = None
    memory_grounding: AgentMemoryGrounding | None = None


class CriticalFinding(BaseModel):
    finding_id: str
    category: Literal[
        "CONTRADICTION",
        "UNSUPPORTED_CONCLUSION",
        "INSUFFICIENT_EVIDENCE",
        "MEMORY_CONFLICT_BLOCKED",
    ]
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    agent_ids: list[str] = Field(default_factory=list)
    subject: str
    description: str
    evidence_sources: list[str] = Field(default_factory=list)
    resolution: str


class CriticalConclusionAssessment(BaseModel):
    agent_id: str
    status: Literal["VALIDATED", "CONDITIONED", "REJECTED"]
    conclusion: str
    live_evidence_sources: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CriticalReview(BaseModel):
    agent_id: Literal["critical-agent"] = "critical-agent"
    enabled: bool = True
    mode: Literal["STANDARD", "STRICT"] = "STANDARD"
    status: Literal["VALIDATED", "CONDITIONED", "REJECTED"] = "VALIDATED"
    reviewed_agent_count: int = Field(default=0, ge=0)
    validated_count: int = Field(default=0, ge=0)
    conditioned_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    contradiction_count: int = Field(default=0, ge=0)
    unsupported_count: int = Field(default=0, ge=0)
    insufficient_evidence_count: int = Field(default=0, ge=0)
    findings: list[CriticalFinding] = Field(default_factory=list)
    assessments: list[CriticalConclusionAssessment] = Field(default_factory=list)
    requires_human_review: bool = False
    summary: str = ""


class AdaptiveReplanSelection(BaseModel):
    agent_id: str
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)


class AdaptiveReplanTrace(BaseModel):
    enabled: bool = False
    triggered: bool = False
    status: Literal[
        "DISABLED",
        "NOT_REQUIRED",
        "NO_ACTION",
        "PLANNED",
        "EXECUTED",
    ] = "NOT_REQUIRED"
    strategy: str = "NONE"
    initial_conclusion_status: Literal[
        "VALIDATED",
        "CONDITIONED",
        "REJECTED",
    ] = "VALIDATED"
    final_conclusion_status: Literal[
        "VALIDATED",
        "CONDITIONED",
        "REJECTED",
    ] = "VALIDATED"
    rounds_executed: int = Field(default=0, ge=0, le=1)
    max_rounds: int = Field(default=1, ge=0, le=1)
    max_additional_agents: int = Field(default=2, ge=0, le=5)
    trigger_finding_ids: list[str] = Field(default_factory=list)
    selections: list[AdaptiveReplanSelection] = Field(default_factory=list)
    added_agents: list[str] = Field(default_factory=list)
    unresolved_finding_ids: list[str] = Field(default_factory=list)
    summary: str = ""


class MemoryInfluence(BaseModel):
    memory_id: str
    agent_id: str | None = None
    memory_type: str
    score: float = Field(ge=0, le=1)
    match_type: str
    excerpt: str


class OrchestratorRequest(BaseModel):
    execution_id: str
    question: str = Field(min_length=3, max_length=2000)
    include_logs: bool = False
    requested_agents: list[str] = Field(default_factory=list)
    max_agents: int = Field(default=3, ge=1, le=10)

    session_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    user_id: str | None = None

    memory_enabled: bool = True
    memory_limit: int = Field(default=8, ge=1, le=20)
    memory_types: list[str] = Field(
        default_factory=lambda: ["EPISODIC", "SEMANTIC", "AGENT"]
    )
    persist_memory: bool = True

    memory_injection_enabled: bool = True
    memory_context_mode: Literal["STRICT", "COLLABORATIVE"] = "STRICT"
    memory_context_min_score: float = Field(default=0.25, ge=0, le=1)
    memory_context_max_items_per_agent: int = Field(default=3, ge=1, le=10)
    memory_context_max_chars_per_agent: int = Field(default=1800, ge=100, le=12000)

    memory_grounding_enabled: bool = True
    memory_grounding_max_items_per_agent: int = Field(default=2, ge=1, le=10)

    critical_validation_enabled: bool = True
    critical_validation_mode: Literal["STANDARD", "STRICT"] = "STANDARD"
    critical_min_live_evidence_sources: int = Field(default=1, ge=0, le=10)
    critical_reject_on_contradiction: bool = True

    adaptive_replanning_enabled: bool = False
    adaptive_replanning_max_additional_agents: int = Field(default=2, ge=1, le=5)
    adaptive_replanning_max_rounds: int = Field(default=1, ge=0, le=1)


class OrchestratorResponse(BaseModel):
    execution_id: str
    session_id: str
    generated_at: datetime
    question: str
    selection_mode: str
    plan: OrchestrationPlan
    selected_agents: list[str] = Field(default_factory=list)
    results: list[AgentTaskResult] = Field(default_factory=list)
    consolidated_summary: str
    requires_human_review: bool
    missing_sources: list[str] = Field(default_factory=list)

    memory_used: bool = False
    memory_provider: str | None = None
    memory_influences: list[MemoryInfluence] = Field(default_factory=list)
    memory_injection_used: bool = False
    memory_context_mode: Literal["STRICT", "COLLABORATIVE"] = "STRICT"
    memory_contexts: list[AgentMemoryContext] = Field(default_factory=list)
    memory_grounding_used: bool = False
    grounded_agent_count: int = Field(default=0, ge=0)

    critical_validation_used: bool = False
    conclusion_status: Literal["VALIDATED", "CONDITIONED", "REJECTED"] = "VALIDATED"
    critical_review: CriticalReview | None = None

    adaptive_replanning_used: bool = False
    adaptive_replanning: AdaptiveReplanTrace | None = None

    persisted_memory_ids: list[str] = Field(default_factory=list)
