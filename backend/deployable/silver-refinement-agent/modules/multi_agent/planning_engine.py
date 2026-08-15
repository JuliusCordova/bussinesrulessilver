from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from .planner import DynamicAgentPlanner
from .planning_models import ExecutionPlan, PlanStep, PlanningRequest
from .registry import AgentRegistry, build_default_registry
from .tool_registry import ToolRegistry, build_default_tool_registry


class PlanningEngine:
    def __init__(
        self,
        registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        selector: DynamicAgentPlanner | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.tool_registry = tool_registry or build_default_tool_registry()
        self.selector = selector or DynamicAgentPlanner(self.registry, self.tool_registry)

    def build(self, request: PlanningRequest) -> ExecutionPlan:
        started = perf_counter()
        strategy, rationale = self._strategy(request.question)
        selected = self.selector.plan(
            question=request.question,
            requested_agents=request.requested_agents,
            max_agents=request.max_agents,
        )
        agent_ids = [item.agent_id for item in selected.selections]
        agent_ids = self._ensure_required_agents(strategy, agent_ids, request.max_agents)
        stages = self._stages(strategy, agent_ids)

        steps: list[PlanStep] = []
        previous_stage_ids: list[str] = []
        parallel_groups: list[list[str]] = []
        for stage_number, stage_agents in enumerate(stages, start=1):
            stage_step_ids: list[str] = []
            for agent_id in stage_agents:
                descriptor = self.registry.get(agent_id)
                if descriptor is None:
                    continue
                step_id = f"step-{stage_number}-{agent_id}"
                stage_step_ids.append(step_id)
                steps.append(
                    PlanStep(
                        step_id=step_id,
                        stage=stage_number,
                        agent_id=agent_id,
                        depends_on=list(previous_stage_ids),
                        tools=list(descriptor.tool_ids),
                        condition="PREVIOUS_STAGE_COMPLETED" if previous_stage_ids else "ALWAYS",
                        can_run_in_parallel=len(stage_agents) > 1,
                    )
                )
            if stage_step_ids:
                parallel_groups.append(stage_step_ids)
                previous_stage_ids = stage_step_ids

        elapsed_ms = max(int((perf_counter() - started) * 1000), 0)
        return ExecutionPlan(
            plan_id=f"plan_{uuid4().hex}",
            execution_id=request.execution_id,
            generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            strategy=strategy,
            rationale=rationale + [f"Selección base: {selected.strategy}."],
            steps=steps,
            parallel_groups=parallel_groups,
            max_parallelism=max((len(group) for group in parallel_groups), default=1),
            planning_time_ms=elapsed_ms,
            requires_human_review=strategy in {"ROOT_CAUSE", "PROMOTION_READINESS", "ROLLBACK_ANALYSIS"},
        )

    @staticmethod
    def _strategy(question: str) -> tuple[str, list[str]]:
        text = question.lower()
        rules = (
            ("ROOT_CAUSE", ("por qué", "porque", "falló", "error", "causa")),
            ("PROMOTION_READINESS", ("promover", "promoción", "producción", "listo para prod")),
            ("ROLLBACK_ANALYSIS", ("rollback", "revertir", "retroceder")),
            ("QUALITY_ANALYSIS", ("calidad", "nulos", "profiling", "conciliación", "reconciliation")),
            ("HEALTH_CHECK", ("salud", "health", "disponibilidad", "plataforma")),
            ("EXECUTION_STATUS", ("estado", "métricas", "pipeline", "ejecución")),
        )
        for strategy, keywords in rules:
            matched = [keyword for keyword in keywords if keyword in text]
            if matched:
                return strategy, [f"La pregunta contiene señales de intención: {', '.join(matched)}."]
        return "EXECUTIVE_SUMMARY", ["No se detectó una intención especializada; se generará un resumen ejecutivo."]

    @staticmethod
    def _ensure_required_agents(strategy: str, selected: list[str], max_agents: int) -> list[str]:
        required = {
            "ROOT_CAUSE": ["execution-agent", "quality-agent", "platform-agent", "recommendation-agent"],
            "PROMOTION_READINESS": ["quality-agent", "governance-agent", "recommendation-agent"],
            "ROLLBACK_ANALYSIS": ["execution-agent", "governance-agent", "recommendation-agent"],
            "QUALITY_ANALYSIS": ["quality-agent", "execution-agent", "recommendation-agent"],
            "HEALTH_CHECK": ["platform-agent", "execution-agent"],
            "EXECUTION_STATUS": ["execution-agent", "recommendation-agent"],
            "EXECUTIVE_SUMMARY": ["execution-agent", "quality-agent", "governance-agent", "recommendation-agent"],
        }.get(strategy, [])
        ordered: list[str] = []
        for agent_id in required + selected:
            if agent_id not in ordered:
                ordered.append(agent_id)
        return ordered[:max_agents]

    @staticmethod
    def _stages(strategy: str, agents: list[str]) -> list[list[str]]:
        patterns = {
            "ROOT_CAUSE": [["execution-agent"], ["quality-agent", "platform-agent"], ["governance-agent"], ["recommendation-agent"]],
            "PROMOTION_READINESS": [["quality-agent", "execution-agent"], ["governance-agent"], ["recommendation-agent"]],
            "ROLLBACK_ANALYSIS": [["execution-agent", "governance-agent"], ["recommendation-agent"]],
            "QUALITY_ANALYSIS": [["execution-agent", "quality-agent"], ["recommendation-agent"]],
            "HEALTH_CHECK": [["execution-agent", "platform-agent"]],
            "EXECUTION_STATUS": [["execution-agent"], ["recommendation-agent"]],
            "EXECUTIVE_SUMMARY": [["execution-agent", "quality-agent", "platform-agent"], ["governance-agent"], ["recommendation-agent"]],
        }.get(strategy, [agents])
        filtered: list[list[str]] = []
        used: set[str] = set()
        for stage in patterns:
            active = [agent for agent in stage if agent in agents and agent not in used]
            if active:
                filtered.append(active)
                used.update(active)
        remaining = [agent for agent in agents if agent not in used]
        if remaining:
            filtered.append(remaining)
        return filtered
