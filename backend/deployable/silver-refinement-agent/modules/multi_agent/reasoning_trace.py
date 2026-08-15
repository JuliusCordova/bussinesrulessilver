from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from .models import OrchestratorRequest, OrchestratorResponse
from .trace_models import (
    DecisionGateTrace,
    MemoryUsageTrace,
    ReasoningTrace,
    ReasoningTraceRecord,
    ReasoningTraceStage,
)


_MEMORY_EVIDENCE_SOURCES = {
    "controlled_memory_context",
    "memory_grounding_trace",
}


class ReasoningTraceBuilder:
    """Build an auditable decision trace without storing private reasoning text."""

    def build(
        self,
        *,
        request: OrchestratorRequest,
        response: OrchestratorResponse,
        started_at: datetime,
        completed_at: datetime,
    ) -> ReasoningTrace:
        trace_id = f"trace_{uuid4().hex}"
        stages: list[ReasoningTraceStage] = []

        def add_stage(
            *,
            stage_type: str,
            actor: str,
            status: str,
            summary: str,
            input_refs: list[str] | None = None,
            output_refs: list[str] | None = None,
            evidence_sources: list[str] | None = None,
            memory_ids: list[str] | None = None,
            decision: str | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            sequence = len(stages) + 1
            stages.append(
                ReasoningTraceStage(
                    stage_id=(
                        f"{trace_id}:{sequence:02d}:"
                        f"{stage_type.lower().replace('_', '-')}"
                    ),
                    sequence=sequence,
                    stage_type=stage_type,
                    actor=actor,
                    status=status,
                    summary=summary,
                    input_refs=input_refs or [],
                    output_refs=output_refs or [],
                    evidence_sources=evidence_sources or [],
                    memory_ids=memory_ids or [],
                    decision=decision,
                    metadata=metadata or {},
                )
            )

        memory_usage = self._build_memory_usage(response)
        retrieved_ids = self._memory_ids(memory_usage, "RETRIEVED")
        injected_ids = self._memory_ids(memory_usage, "INJECTED")
        applied_ids = self._memory_ids(memory_usage, "APPLIED")
        blocked_ids = self._memory_ids(memory_usage, "BLOCKED")
        evidence_sources = self._evidence_sources(response)

        add_stage(
            stage_type="REQUEST",
            actor="agent-supervisor",
            status="COMPLETED",
            summary="Solicitud aceptada y correlacionada con sesión y ejecución.",
            input_refs=[response.execution_id, response.session_id],
            output_refs=["orchestration-request"],
            metadata={
                "include_logs": request.include_logs,
                "requested_agent_count": len(request.requested_agents),
                "max_agents": request.max_agents,
            },
        )

        add_stage(
            stage_type="MEMORY_RETRIEVAL",
            actor="shared-memory-service",
            status="COMPLETED" if response.memory_used else "SKIPPED",
            summary=(
                f"Se recuperaron {len(response.memory_influences)} memorias candidatas."
                if response.memory_used
                else "No se recuperaron memorias candidatas relevantes."
            ),
            input_refs=["question-fingerprint", response.execution_id],
            output_refs=["memory-influences"],
            memory_ids=retrieved_ids,
            decision=(
                "MEMORY_CANDIDATES_AVAILABLE"
                if response.memory_used
                else "NO_RELEVANT_MEMORY"
            ),
            metadata={
                "provider": response.memory_provider,
                "memory_enabled": request.memory_enabled,
                "retrieved_count": len(retrieved_ids),
            },
        )

        add_stage(
            stage_type="PLANNING",
            actor="dynamic-agent-planner",
            status="COMPLETED",
            summary=(
                f"Plan {response.plan.strategy} seleccionó "
                f"{len(response.plan.selections)} especialistas iniciales."
            ),
            input_refs=["question-fingerprint", "memory-influences"],
            output_refs=[item.agent_id for item in response.plan.selections],
            decision=response.plan.strategy,
            metadata={
                "fallback_used": response.plan.fallback_used,
                "selection_scores": {
                    item.agent_id: item.score for item in response.plan.selections
                },
            },
        )

        for result in response.results:
            result_sources = sorted(
                {
                    str(item.get("source"))
                    for item in result.evidence
                    if item.get("source")
                    and item.get("source") not in _MEMORY_EVIDENCE_SOURCES
                }
            )
            result_status = (
                "COMPLETED" if result.status == "COMPLETED" else "REQUIRES_REVIEW"
            )
            add_stage(
                stage_type="SPECIALIST_EXECUTION",
                actor=result.agent_id,
                status=result_status,
                summary=result.summary,
                input_refs=result.tools_used,
                output_refs=[f"agent-result:{result.agent_id}"],
                evidence_sources=result_sources,
                memory_ids=[
                    item.memory_id
                    for item in memory_usage
                    if item.agent_id == result.agent_id
                    and item.action in {"INJECTED", "APPLIED", "BLOCKED"}
                ],
                decision=result.status,
                metadata={
                    "tools_used": result.tools_used,
                    "warning_count": len(result.warnings),
                    "recommendation_count": len(result.recommendations),
                },
            )

        grounding_status = "COMPLETED" if response.memory_grounding_used else "SKIPPED"
        add_stage(
            stage_type="MEMORY_GROUNDING",
            actor="memory-grounding-engine",
            status=grounding_status,
            summary=(
                f"Se aplicaron {len(applied_ids)} memorias y se bloquearon "
                f"{len(blocked_ids)} por política de evidencia."
            ),
            input_refs=injected_ids,
            output_refs=applied_ids + blocked_ids,
            memory_ids=injected_ids + applied_ids + blocked_ids,
            decision="CURRENT_EVIDENCE_WINS",
            metadata={
                "injected_count": len(injected_ids),
                "applied_count": len(applied_ids),
                "blocked_count": len(blocked_ids),
                "grounded_agent_count": response.grounded_agent_count,
            },
        )

        critical_review = response.critical_review
        if response.critical_validation_used and critical_review is not None:
            critical_status = {
                "VALIDATED": "COMPLETED",
                "CONDITIONED": "REQUIRES_REVIEW",
                "REJECTED": "BLOCKED",
            }[critical_review.status]
            add_stage(
                stage_type="CRITICAL_VALIDATION",
                actor="critical-agent",
                status=critical_status,
                summary=critical_review.summary,
                input_refs=[f"agent-result:{item.agent_id}" for item in response.results],
                output_refs=[item.finding_id for item in critical_review.findings],
                evidence_sources=evidence_sources,
                decision=critical_review.status,
                metadata={
                    "reviewed_agent_count": critical_review.reviewed_agent_count,
                    "contradiction_count": critical_review.contradiction_count,
                    "unsupported_count": critical_review.unsupported_count,
                    "insufficient_evidence_count": (
                        critical_review.insufficient_evidence_count
                    ),
                },
            )
        else:
            add_stage(
                stage_type="CRITICAL_VALIDATION",
                actor="critical-agent",
                status="SKIPPED",
                summary="La validación crítica fue deshabilitada para esta solicitud.",
                decision="DISABLED",
            )

        replanning = response.adaptive_replanning
        if replanning is None or replanning.status in {"DISABLED", "NOT_REQUIRED"}:
            replan_stage_status = "SKIPPED"
        elif replanning.status == "NO_ACTION":
            replan_stage_status = "REQUIRES_REVIEW"
        else:
            replan_stage_status = "COMPLETED"
        add_stage(
            stage_type="ADAPTIVE_REPLANNING",
            actor="adaptive-replanner",
            status=replan_stage_status,
            summary=(
                replanning.summary
                if replanning is not None
                else "No se generó una traza de replanificación adaptativa."
            ),
            input_refs=(
                replanning.trigger_finding_ids if replanning is not None else []
            ),
            output_refs=(replanning.added_agents if replanning is not None else []),
            decision=(replanning.status if replanning is not None else "DISABLED"),
            metadata=(
                {
                    "strategy": replanning.strategy,
                    "rounds_executed": replanning.rounds_executed,
                    "initial_conclusion_status": (
                        replanning.initial_conclusion_status
                    ),
                    "final_conclusion_status": replanning.final_conclusion_status,
                    "unresolved_finding_ids": replanning.unresolved_finding_ids,
                }
                if replanning is not None
                else {}
            ),
        )

        add_stage(
            stage_type="HUMAN_REVIEW_GATE",
            actor="agent-supervisor",
            status=(
                "REQUIRES_REVIEW"
                if response.requires_human_review
                else "COMPLETED"
            ),
            summary=(
                "La respuesta requiere revisión humana antes de una acción autónoma."
                if response.requires_human_review
                else "No se elevó un gate adicional de revisión humana."
            ),
            input_refs=["critical-review", "adaptive-replanning"],
            output_refs=["human-review-required"],
            decision=(
                "REQUIRED" if response.requires_human_review else "NOT_REQUIRED"
            ),
        )

        add_stage(
            stage_type="PERSISTENCE",
            actor="shared-memory-service",
            status=("COMPLETED" if response.persisted_memory_ids else "SKIPPED"),
            summary=(
                f"Se persistieron {len(response.persisted_memory_ids)} eventos "
                "operacionales previos a la traza."
            ),
            output_refs=response.persisted_memory_ids,
            memory_ids=response.persisted_memory_ids,
            decision=(
                "PERSISTED" if response.persisted_memory_ids else "NOT_REQUESTED"
            ),
        )

        add_stage(
            stage_type="FINAL_RESPONSE",
            actor="agent-supervisor",
            status=(
                "BLOCKED"
                if response.conclusion_status == "REJECTED"
                else (
                    "REQUIRES_REVIEW"
                    if response.conclusion_status == "CONDITIONED"
                    else "COMPLETED"
                )
            ),
            summary="Respuesta consolidada con procedencia estructurada.",
            input_refs=["critical-review", "adaptive-replanning", "human-review-gate"],
            output_refs=["orchestrator-response"],
            evidence_sources=evidence_sources,
            memory_ids=applied_ids,
            decision=response.conclusion_status,
        )

        decision_gates = self._decision_gates(response)
        duration_ms = max(
            0,
            int((completed_at - started_at).total_seconds() * 1000),
        )
        critical_finding_ids = (
            [item.finding_id for item in critical_review.findings]
            if critical_review is not None
            else []
        )
        adaptive_trigger_ids = (
            replanning.trigger_finding_ids if replanning is not None else []
        )

        return ReasoningTrace(
            trace_id=trace_id,
            correlation_id=f"{response.session_id}:{response.execution_id}",
            session_id=response.session_id,
            execution_id=response.execution_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            question_fingerprint=sha256(request.question.encode("utf-8")).hexdigest(),
            stages=stages,
            agent_path=(
                response.selected_agents
                + (["critical-agent"] if response.critical_validation_used else [])
            ),
            evidence_sources=evidence_sources,
            memory_usage=memory_usage,
            decision_gates=decision_gates,
            conclusion_status=response.conclusion_status,
            requires_human_review=response.requires_human_review,
            final_provenance={
                "plan_strategy": response.plan.strategy,
                "selected_agents": response.selected_agents,
                "live_evidence_sources": evidence_sources,
                "retrieved_memory_ids": retrieved_ids,
                "injected_memory_ids": injected_ids,
                "applied_memory_ids": applied_ids,
                "blocked_memory_ids": blocked_ids,
                "critical_finding_ids": critical_finding_ids,
                "adaptive_trigger_finding_ids": adaptive_trigger_ids,
                "persisted_memory_ids": response.persisted_memory_ids,
                "memory_provider": response.memory_provider,
                "evidence_precedence": "CURRENT_EVIDENCE_WINS",
            },
        )

    @staticmethod
    def _memory_ids(items: list[MemoryUsageTrace], action: str) -> list[str]:
        return list(dict.fromkeys(item.memory_id for item in items if item.action == action))

    @staticmethod
    def _evidence_sources(response: OrchestratorResponse) -> list[str]:
        return sorted(
            {
                str(item.get("source"))
                for result in response.results
                for item in result.evidence
                if item.get("source")
                and item.get("source") not in _MEMORY_EVIDENCE_SOURCES
            }
        )

    @staticmethod
    def _build_memory_usage(response: OrchestratorResponse) -> list[MemoryUsageTrace]:
        usage: list[MemoryUsageTrace] = []
        for item in response.memory_influences:
            usage.append(
                MemoryUsageTrace(
                    memory_id=item.memory_id,
                    action="RETRIEVED",
                    memory_type=item.memory_type,
                    source_agent_id=item.agent_id,
                    score=item.score,
                    reason=item.match_type,
                )
            )

        for context in response.memory_contexts:
            for item in context.memories:
                usage.append(
                    MemoryUsageTrace(
                        memory_id=item.memory_id,
                        action="INJECTED",
                        memory_type=item.memory_type,
                        agent_id=context.agent_id,
                        source_agent_id=item.source_agent_id,
                        score=item.score,
                        reason=item.injection_reason,
                    )
                )

        for result in response.results:
            if result.memory_grounding is None:
                continue
            for decision in result.memory_grounding.decisions:
                usage.append(
                    MemoryUsageTrace(
                        memory_id=decision.memory_id,
                        action=decision.status,
                        memory_type=decision.memory_type,
                        agent_id=result.agent_id,
                        source_agent_id=decision.source_agent_id,
                        score=decision.score,
                        reason=decision.reason,
                        evidence_precedence=(
                            result.memory_grounding.evidence_precedence
                        ),
                    )
                )
        return usage

    @staticmethod
    def _decision_gates(response: OrchestratorResponse) -> list[DecisionGateTrace]:
        critical_review = response.critical_review
        replanning = response.adaptive_replanning
        critical_findings = (
            [item.finding_id for item in critical_review.findings]
            if critical_review is not None
            else []
        )

        critical_status = "NOT_APPLICABLE"
        critical_decision = "DISABLED"
        if response.critical_validation_used and critical_review is not None:
            critical_decision = critical_review.status
            critical_status = {
                "VALIDATED": "PASSED",
                "CONDITIONED": "REQUIRES_REVIEW",
                "REJECTED": "BLOCKED",
            }[critical_review.status]

        replanning_status = "NOT_APPLICABLE"
        replanning_decision = "DISABLED"
        replanning_findings: list[str] = []
        if replanning is not None:
            replanning_decision = replanning.status
            replanning_findings = replanning.trigger_finding_ids
            if replanning.status in {"EXECUTED", "NOT_REQUIRED"}:
                replanning_status = "PASSED"
            elif replanning.status == "NO_ACTION":
                replanning_status = "REQUIRES_REVIEW"
            elif replanning.status == "PLANNED":
                replanning_status = "REQUIRES_REVIEW"

        return [
            DecisionGateTrace(
                gate_id="evidence-precedence",
                gate_type="EVIDENCE_PRECEDENCE",
                decision="CURRENT_EVIDENCE_WINS",
                status="PASSED",
                reasons=[
                    "La memoria histórica no puede invalidar evidencia operacional actual."
                ],
            ),
            DecisionGateTrace(
                gate_id="critical-validation",
                gate_type="CRITICAL_VALIDATION",
                decision=critical_decision,
                status=critical_status,
                finding_ids=critical_findings,
            ),
            DecisionGateTrace(
                gate_id="adaptive-replanning",
                gate_type="ADAPTIVE_REPLANNING",
                decision=replanning_decision,
                status=replanning_status,
                finding_ids=replanning_findings,
            ),
            DecisionGateTrace(
                gate_id="human-review",
                gate_type="HUMAN_REVIEW",
                decision=(
                    "REQUIRED" if response.requires_human_review else "NOT_REQUIRED"
                ),
                status=(
                    "REQUIRES_REVIEW"
                    if response.requires_human_review
                    else "PASSED"
                ),
                finding_ids=critical_findings,
            ),
        ]


def trace_records_from_memories(records) -> list[ReasoningTraceRecord]:
    traces: list[ReasoningTraceRecord] = []
    for record in records:
        metadata = record.metadata or {}
        if metadata.get("kind") != "reasoning-trace":
            continue
        trace_payload = metadata.get("trace")
        if not isinstance(trace_payload, dict):
            continue
        traces.append(
            ReasoningTraceRecord(
                memory_id=record.memory_id,
                created_at=record.created_at,
                trace=ReasoningTrace.model_validate(trace_payload),
            )
        )
    return traces
