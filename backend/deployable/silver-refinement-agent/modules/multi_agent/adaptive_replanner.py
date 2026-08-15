from __future__ import annotations

from collections import defaultdict

from .models import (
    AdaptiveReplanSelection,
    AdaptiveReplanTrace,
    CriticalFinding,
    CriticalReview,
)
from .registry import AgentRegistry


class AdaptiveReplanner:
    """Builds one bounded specialist replan from critical-agent findings.

    The engine never executes agents itself. It maps typed findings to enabled
    specialists, excludes validators and already executed specialists, and emits
    a traceable plan that the Supervisor may execute once.
    """

    SOURCE_AGENT_MAP = {
        "silver_execution": "execution-agent",
        "current_execution_status": "execution-agent",
        "execution_metrics": "quality-agent",
        "data_quality": "quality-agent",
        "profiling": "quality-agent",
        "reconciliation": "quality-agent",
        "governance": "governance-agent",
        "platform_health": "platform-agent",
        "diagnosis": "recommendation-agent",
    }

    SUBJECT_AGENT_MAP = {
        "execution": "execution-agent",
        "quality": "quality-agent",
        "governance": "governance-agent",
        "platform": "platform-agent",
        "diagnosis": "recommendation-agent",
        "conclusion": "recommendation-agent",
        "evidence": "recommendation-agent",
    }

    COMPLEMENT_AGENT_MAP = {
        "execution-agent": ["recommendation-agent", "platform-agent"],
        "quality-agent": ["execution-agent", "recommendation-agent"],
        "governance-agent": ["execution-agent", "recommendation-agent"],
        "platform-agent": ["execution-agent", "recommendation-agent"],
        "recommendation-agent": ["execution-agent", "quality-agent"],
    }

    SEVERITY_SCORE = {
        "CRITICAL": 1.0,
        "WARNING": 0.75,
        "INFO": 0.25,
    }

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def plan(
        self,
        *,
        review: CriticalReview,
        selected_agent_ids: list[str],
        enabled: bool = False,
        max_additional_agents: int = 2,
        max_rounds: int = 1,
    ) -> AdaptiveReplanTrace:
        trace = AdaptiveReplanTrace(
            enabled=enabled,
            initial_conclusion_status=review.status,
            final_conclusion_status=review.status,
            max_rounds=max_rounds,
            max_additional_agents=max_additional_agents,
        )

        if not enabled:
            trace.status = "DISABLED"
            trace.summary = "La replanificación adaptativa está deshabilitada."
            return trace

        if review.status == "VALIDATED":
            trace.status = "NOT_REQUIRED"
            trace.summary = "La validación crítica no requiere una nueva planificación."
            return trace

        trigger_findings = [
            finding for finding in review.findings if finding.severity != "INFO"
        ]
        trace.trigger_finding_ids = [item.finding_id for item in trigger_findings]

        if max_rounds < 1 or max_additional_agents < 1:
            trace.status = "NO_ACTION"
            trace.strategy = "REPLAN_BUDGET_EXHAUSTED"
            trace.unresolved_finding_ids = trace.trigger_finding_ids.copy()
            trace.summary = "No existe presupuesto para ejecutar una ronda adaptativa."
            return trace

        selected_set = set(selected_agent_ids)
        candidate_findings: dict[str, set[str]] = defaultdict(set)
        candidate_reasons: dict[str, set[str]] = defaultdict(set)
        candidate_scores: dict[str, float] = {}

        for finding in trigger_findings:
            for agent_id, reason in self._candidate_agents(finding):
                descriptor = self.registry.get(agent_id)
                if (
                    descriptor is None
                    or not descriptor.enabled
                    or descriptor.execution_phase != "SPECIALIST"
                    or agent_id in selected_set
                ):
                    continue
                candidate_findings[agent_id].add(finding.finding_id)
                candidate_reasons[agent_id].add(reason)
                candidate_scores[agent_id] = max(
                    candidate_scores.get(agent_id, 0.0),
                    self.SEVERITY_SCORE.get(finding.severity, 0.5),
                )

        ranked = sorted(
            candidate_scores,
            key=lambda agent_id: (-candidate_scores[agent_id], agent_id),
        )[:max_additional_agents]

        if not ranked:
            trace.status = "NO_ACTION"
            trace.strategy = "NO_ADDITIONAL_SPECIALIST"
            trace.unresolved_finding_ids = trace.trigger_finding_ids.copy()
            trace.summary = (
                "El agente crítico solicitó evidencia adicional, pero no existe un "
                "especialista nuevo elegible dentro de la política actual."
            )
            return trace

        trace.status = "PLANNED"
        trace.triggered = True
        trace.strategy = "CRITICAL_FEEDBACK"
        trace.selections = [
            AdaptiveReplanSelection(
                agent_id=agent_id,
                score=candidate_scores[agent_id],
                reasons=sorted(candidate_reasons[agent_id]),
                finding_ids=sorted(candidate_findings[agent_id]),
                selected_tools=(self.registry.get(agent_id).tool_ids),
            )
            for agent_id in ranked
        ]
        trace.summary = (
            f"Se planificó una ronda adaptativa con {len(trace.selections)} "
            "especialistas adicionales a partir de hallazgos críticos tipados."
        )
        return trace

    def _candidate_agents(self, finding: CriticalFinding) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []

        subject_prefix = finding.subject.split(".", 1)[0].lower()
        subject_agent = self.SUBJECT_AGENT_MAP.get(subject_prefix)
        if subject_agent:
            candidates.append(
                (
                    subject_agent,
                    f"El hallazgo {finding.finding_id} requiere autoridad sobre "
                    f"{subject_prefix}.",
                )
            )

        for source in finding.evidence_sources:
            source_agent = self.SOURCE_AGENT_MAP.get(source)
            if source_agent:
                candidates.append(
                    (
                        source_agent,
                        f"El hallazgo {finding.finding_id} requiere la fuente viva "
                        f"{source}.",
                    )
                )

        for affected_agent in finding.agent_ids:
            for complement in self.COMPLEMENT_AGENT_MAP.get(affected_agent, []):
                candidates.append(
                    (
                        complement,
                        f"El hallazgo {finding.finding_id} requiere evidencia "
                        f"complementaria para {affected_agent}.",
                    )
                )

        if finding.category in {
            "UNSUPPORTED_CONCLUSION",
            "INSUFFICIENT_EVIDENCE",
        }:
            candidates.append(
                (
                    "recommendation-agent",
                    f"El hallazgo {finding.finding_id} requiere una síntesis "
                    "determinística adicional.",
                )
            )

        deduplicated: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            deduplicated.append(candidate)
        return deduplicated
