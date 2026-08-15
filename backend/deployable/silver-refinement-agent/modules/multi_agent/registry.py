from __future__ import annotations

from .models import AgentDescriptor


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}

    def register(self, descriptor: AgentDescriptor) -> None:
        self._agents[descriptor.agent_id] = descriptor

    def get(self, agent_id: str) -> AgentDescriptor | None:
        return self._agents.get(agent_id)

    def list(self, enabled_only: bool = True) -> list[AgentDescriptor]:
        agents = list(self._agents.values())
        if enabled_only:
            agents = [agent for agent in agents if agent.enabled]
        return sorted(agents, key=lambda agent: agent.agent_id)

    def resolve(self, requested_agents: list[str] | None = None) -> list[AgentDescriptor]:
        if requested_agents:
            return [
                self._agents[item]
                for item in requested_agents
                if item in self._agents and self._agents[item].enabled
            ]
        return self.list(enabled_only=True)


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    for descriptor in (
        AgentDescriptor(
            agent_id="execution-agent",
            name="Execution Agent",
            domain="execution",
            description="Analiza estado, métricas y eventos de ejecución.",
            capabilities=["execution_status", "metrics", "timeline"],
            tool_ids=["get-execution", "get-metrics"],
        ),
        AgentDescriptor(
            agent_id="quality-agent",
            name="Quality Agent",
            domain="quality",
            description="Analiza señales de calidad, profiling y reconciliación.",
            capabilities=["data_quality", "profiling", "reconciliation"],
            tool_ids=["get-metrics", "get-quality-signals"],
        ),
        AgentDescriptor(
            agent_id="governance-agent",
            name="Governance Agent",
            domain="governance",
            description="Analiza aprobaciones, promociones y rollback.",
            capabilities=["reviews", "promotions", "rollbacks"],
            tool_ids=["get-governance-history"],
        ),
        AgentDescriptor(
            agent_id="platform-agent",
            name="Platform Agent",
            domain="platform",
            description="Analiza salud de componentes y dependencias de plataforma.",
            capabilities=["platform_health", "availability"],
            tool_ids=["get-platform-health"],
        ),
        AgentDescriptor(
            agent_id="recommendation-agent",
            name="Recommendation Agent",
            domain="remediation",
            description="Consolida diagnóstico y plan de remediación.",
            capabilities=["diagnosis", "remediation"],
            tool_ids=["build-remediation-plan"],
        ),
        AgentDescriptor(
            agent_id="critical-agent",
            name="Critical Conclusion Agent",
            domain="critical-validation",
            description=(
                "Valida soporte, consistencia y contradicciones antes de publicar "
                "la conclusión consolidada."
            ),
            capabilities=[
                "conclusion_validation",
                "contradiction_detection",
                "evidence_sufficiency",
                "human_review_gate",
            ],
            tool_ids=[],
            execution_phase="VALIDATOR",
            version="7.5.5",
        ),
    ):
        registry.register(descriptor)
    return registry
