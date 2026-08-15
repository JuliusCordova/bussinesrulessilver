from __future__ import annotations

import unicodedata

from .models import AgentSelection, OrchestrationPlan
from .registry import AgentRegistry
from .tool_registry import ToolRegistry


class DynamicAgentPlanner:
    def __init__(self, agent_registry: AgentRegistry, tool_registry: ToolRegistry) -> None:
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.lower())
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @staticmethod
    def _is_specialist(descriptor) -> bool:
        return descriptor is not None and descriptor.execution_phase == "SPECIALIST"

    def plan(
        self,
        question: str,
        requested_agents: list[str] | None = None,
        max_agents: int = 3,
        memory_agent_scores: dict[str, float] | None = None,
    ) -> OrchestrationPlan:
        if requested_agents:
            selections = []
            for descriptor in self.agent_registry.resolve(requested_agents):
                if not self._is_specialist(descriptor):
                    continue
                selections.append(
                    AgentSelection(
                        agent_id=descriptor.agent_id,
                        score=1.0,
                        reasons=["Selección explícita solicitada por el usuario."],
                        selected_tools=descriptor.tool_ids,
                    )
                )
            return OrchestrationPlan(
                strategy="EXPLICIT",
                selections=selections,
                fallback_used=False,
            )

        normalized_question = self._normalize(question)
        scores: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}
        selected_tools: dict[str, list[str]] = {}

        for tool in self.tool_registry.list():
            matches = [
                keyword
                for keyword in tool.keywords
                if self._normalize(keyword) in normalized_question
            ]
            if not matches:
                continue
            for agent_id in tool.agent_ids:
                descriptor = self.agent_registry.get(agent_id)
                if not self._is_specialist(descriptor):
                    continue
                increment = min(0.25 + (0.1 * len(matches)), 0.65)
                scores[agent_id] = min(scores.get(agent_id, 0.0) + increment, 1.0)
                reasons.setdefault(agent_id, []).append(
                    f"La herramienta {tool.tool_id} coincide con: {', '.join(matches)}."
                )
                selected_tools.setdefault(agent_id, []).append(tool.tool_id)

        valid_memory_scores = {
            agent_id: max(min(float(score), 1.0), 0.0)
            for agent_id, score in (memory_agent_scores or {}).items()
            if self._is_specialist(self.agent_registry.get(agent_id))
        }
        for agent_id, memory_score in valid_memory_scores.items():
            memory_boost = min(memory_score * 0.35, 0.35)
            scores[agent_id] = min(scores.get(agent_id, 0.0) + memory_boost, 1.0)
            reasons.setdefault(agent_id, []).append(
                f"La memoria compartida aportó relevancia {memory_score:.2f} para este agente."
            )
            descriptor = self.agent_registry.get(agent_id)
            if descriptor is not None:
                selected_tools.setdefault(agent_id, []).extend(descriptor.tool_ids)

        if scores:
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[
                :max_agents
            ]
            selections = [
                AgentSelection(
                    agent_id=agent_id,
                    score=round(score, 2),
                    reasons=reasons.get(agent_id, []),
                    selected_tools=sorted(
                        set(
                            selected_tools.get(agent_id)
                            or (
                                self.agent_registry.get(agent_id).tool_ids
                                if self.agent_registry.get(agent_id)
                                else []
                            )
                        )
                    ),
                )
                for agent_id, score in ranked
            ]
            return OrchestrationPlan(
                strategy="MEMORY_AWARE" if valid_memory_scores else "DYNAMIC_KEYWORD",
                selections=selections,
                fallback_used=False,
            )

        fallback_ids = ["execution-agent", "recommendation-agent"][:max_agents]
        selections = [
            AgentSelection(
                agent_id=agent_id,
                score=0.25,
                reasons=[
                    "No hubo coincidencias suficientes; se aplicó el conjunto seguro por defecto."
                ],
                selected_tools=(
                    self.agent_registry.get(agent_id).tool_ids
                    if self.agent_registry.get(agent_id)
                    else []
                ),
            )
            for agent_id in fallback_ids
        ]
        return OrchestrationPlan(
            strategy="SAFE_FALLBACK",
            selections=selections,
            fallback_used=True,
        )
