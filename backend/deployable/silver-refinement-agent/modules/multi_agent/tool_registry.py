from __future__ import annotations

from .models import ToolDescriptor


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        self._tools[descriptor.tool_id] = descriptor

    def get(self, tool_id: str) -> ToolDescriptor | None:
        return self._tools.get(tool_id)

    def list(self, enabled_only: bool = True) -> list[ToolDescriptor]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        return sorted(tools, key=lambda tool: tool.tool_id)

    def for_agent(self, agent_id: str) -> list[ToolDescriptor]:
        return [tool for tool in self.list() if agent_id in tool.agent_ids]


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for descriptor in (
        ToolDescriptor(tool_id="get-execution", name="Get Execution", domain="execution", description="Obtiene estado y metadatos de una ejecución.", agent_ids=["execution-agent"], keywords=["ejecución", "execution", "estado", "pipeline", "falló", "failed"]),
        ToolDescriptor(tool_id="get-metrics", name="Get Metrics", domain="execution", description="Consulta métricas operativas y de procesamiento.", agent_ids=["execution-agent", "quality-agent"], keywords=["métricas", "metrics", "filas", "rows", "rendimiento"]),
        ToolDescriptor(tool_id="get-quality-signals", name="Get Quality Signals", domain="quality", description="Consulta Data Quality, Profiling y Reconciliation.", agent_ids=["quality-agent"], keywords=["calidad", "quality", "nulos", "duplicados", "profiling", "reconciliation", "conciliación"]),
        ToolDescriptor(tool_id="get-governance-history", name="Get Governance History", domain="governance", description="Consulta revisiones, promociones y rollbacks.", agent_ids=["governance-agent"], keywords=["gobierno", "governance", "aprobación", "promoción", "rollback", "auditoría"]),
        ToolDescriptor(tool_id="get-platform-health", name="Get Platform Health", domain="platform", description="Consulta salud y disponibilidad de componentes.", agent_ids=["platform-agent"], keywords=["plataforma", "platform", "salud", "health", "dataproc", "bigquery", "cloud run", "storage"]),
        ToolDescriptor(tool_id="build-remediation-plan", name="Build Remediation Plan", domain="remediation", description="Construye diagnóstico y plan de remediación.", agent_ids=["recommendation-agent"], keywords=["recomienda", "recomendación", "qué hacer", "siguiente paso", "remediación", "riesgo", "acción"]),
    ):
        registry.register(descriptor)
    return registry
