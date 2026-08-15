from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .models import (
    AgentMemoryContext,
    AgentMemoryGrounding,
    AgentTaskResult,
    GroundedMemoryDecision,
    InjectedMemory,
)


class MemoryGroundingEngine:
    """Applies injected memory to an agent result without overriding live evidence."""

    POSITIVE_STATUS = {
        "SUCCEEDED",
        "SUCCESS",
        "COMPLETED",
        "HEALTHY",
        "APPROVED",
        "PASSED",
        "READY",
    }
    NEGATIVE_STATUS = {
        "FAILED",
        "FAILURE",
        "ERROR",
        "UNHEALTHY",
        "REJECTED",
        "BLOCKED",
        "CRITICAL",
    }
    NON_LIVE_EVIDENCE_SOURCES = {
        "controlled_memory_context",
        "memory_grounding_trace",
    }

    CONTRIBUTION_PREFIX = {
        "SEMANTIC": "Regla reutilizable",
        "EPISODIC": "Antecedente operativo",
        "AGENT": "Observación previa de agente",
        "WORKING": "Contexto temporal previo",
    }

    def ground(
        self,
        *,
        result: AgentTaskResult,
        memory_context: AgentMemoryContext,
        enabled: bool = True,
        max_items: int = 2,
    ) -> AgentTaskResult:
        grounding = AgentMemoryGrounding(
            agent_id=result.agent_id,
            enabled=enabled,
            candidate_count=memory_context.injected_count,
            max_items=max_items,
        )
        result.memory_context = memory_context

        if not enabled or not memory_context.memories:
            grounding.blocked_count = memory_context.injected_count if not enabled else 0
            if not enabled:
                grounding.decisions = [
                    self._decision(memory, status="BLOCKED", reason="GROUNDING_DISABLED")
                    for memory in memory_context.memories
                ]
            result.memory_grounding = grounding
            self._append_trace(result, grounding)
            return result

        current_polarity = self._current_evidence_polarity(result)
        applied = 0

        for memory in memory_context.memories:
            # Safety decisions must inspect every candidate before the application
            # budget is enforced. The budget limits how many compatible memories
            # can influence the result; it must never hide a contradiction from the
            # auditable grounding trace.
            memory_polarity = self._status_polarity(memory.excerpt)
            if self._conflicts(current_polarity, memory_polarity):
                grounding.conflict_count += 1
                grounding.decisions.append(
                    self._decision(
                        memory,
                        status="BLOCKED",
                        reason="CONFLICT_WITH_CURRENT_EVIDENCE",
                    )
                )
                continue

            if applied >= max_items:
                grounding.decisions.append(
                    self._decision(memory, status="BLOCKED", reason="GROUNDING_ITEM_BUDGET")
                )
                continue

            contribution = self._contribution(memory)
            grounding.historical_context.append(contribution)
            grounding.decisions.append(
                self._decision(
                    memory,
                    status="APPLIED",
                    reason=self._application_reason(memory),
                    contribution=contribution,
                )
            )
            applied += 1

        grounding.applied_count = applied
        grounding.blocked_count = len(grounding.decisions) - applied
        result.memory_grounding = grounding

        if grounding.historical_context:
            result.summary = (
                f"{result.summary} Contexto histórico aplicado: "
                + " ".join(grounding.historical_context)
            )

        if grounding.conflict_count:
            result.warnings.append(
                f"Se bloquearon {grounding.conflict_count} memorias por conflicto "
                "con la evidencia actual; prevaleció la evidencia operativa."
            )

        self._append_trace(result, grounding)
        return result

    @staticmethod
    def _decision(
        memory: InjectedMemory,
        *,
        status: str,
        reason: str,
        contribution: str | None = None,
    ) -> GroundedMemoryDecision:
        return GroundedMemoryDecision(
            memory_id=memory.memory_id,
            memory_type=memory.memory_type,
            source_agent_id=memory.source_agent_id,
            score=memory.score,
            status=status,
            reason=reason,
            contribution=contribution,
        )

    def _contribution(self, memory: InjectedMemory) -> str:
        prefix = self.CONTRIBUTION_PREFIX.get(
            memory.memory_type.upper(),
            "Memoria relevante",
        )
        excerpt = re.sub(r"\s+", " ", memory.excerpt.strip())
        if len(excerpt) > 220:
            excerpt = excerpt[:219].rstrip() + "…"
        return f"{prefix}: {excerpt}"

    @staticmethod
    def _application_reason(memory: InjectedMemory) -> str:
        memory_type = memory.memory_type.upper()
        if memory_type == "SEMANTIC":
            return "REUSABLE_RULE_APPLIED"
        if memory_type == "EPISODIC":
            return "HISTORICAL_PRECEDENT_APPLIED"
        if memory_type == "AGENT":
            return "PRIOR_AGENT_OBSERVATION_APPLIED"
        return "RELEVANT_MEMORY_APPLIED"

    def _current_evidence_polarity(self, result: AgentTaskResult) -> set[str]:
        """Resolve current operational polarity from live evidence only.

        The agent task status is intentionally excluded because values such as
        COMPLETED describe task execution, not the domain state of the pipeline.
        Memory-derived evidence is also excluded so a candidate memory cannot
        contaminate the live-evidence polarity used to evaluate that same memory.
        """

        live_evidence = [
            item
            for item in result.evidence
            if str(item.get("source", "")).lower()
            not in self.NON_LIVE_EVIDENCE_SOURCES
        ]
        current_payload = {
            "summary": result.summary,
            "evidence": live_evidence,
        }
        return self._status_polarity(self._flatten(current_payload))

    def _status_polarity(self, text: str) -> set[str]:
        tokens = set(re.findall(r"[A-ZÁÉÍÓÚÑ_]+", text.upper()))
        polarity: set[str] = set()
        if tokens & self.POSITIVE_STATUS:
            polarity.add("POSITIVE")
        if tokens & self.NEGATIVE_STATUS:
            polarity.add("NEGATIVE")
        return polarity

    @staticmethod
    def _conflicts(current: set[str], memory: set[str]) -> bool:
        return (
            current == {"POSITIVE"} and memory == {"NEGATIVE"}
        ) or (
            current == {"NEGATIVE"} and memory == {"POSITIVE"}
        )

    def _flatten(self, payload: Any) -> str:
        values: list[str] = []
        self._collect(payload, values)
        return " ".join(values)

    def _collect(self, payload: Any, values: list[str]) -> None:
        if payload is None:
            return
        if isinstance(payload, dict):
            for key, value in payload.items():
                values.append(str(key))
                self._collect(value, values)
            return
        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            for item in payload:
                self._collect(item, values)
            return
        values.append(str(payload))

    @staticmethod
    def _append_trace(
        result: AgentTaskResult,
        grounding: AgentMemoryGrounding,
    ) -> None:
        result.evidence.append(
            {
                "source": "memory_grounding_trace",
                "payload": grounding.model_dump(mode="json"),
            }
        )
