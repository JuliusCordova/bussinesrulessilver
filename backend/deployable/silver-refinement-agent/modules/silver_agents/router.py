from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, status
from google.adk.agents import BaseAgent

from .agents import (
    build_business_rule_validator_agent,
    build_notebook_generator_agent,
    build_quality_rule_advisor_agent,
    build_silver_orchestrator,
    build_table_profiler_agent,
)
from .models import AgentDescriptor, AgentRunRequest, AgentRunResponse
from .service import SilverAgentRunner


router = APIRouter(prefix="/silver-agents", tags=["silver-agents"])

_FACTORIES: dict[str, Callable[[], BaseAgent]] = {
    "table-profiler": build_table_profiler_agent,
    "quality-rule-advisor": build_quality_rule_advisor_agent,
    "business-rule-validator": build_business_rule_validator_agent,
    "notebook-generator": build_notebook_generator_agent,
    "orchestrator": build_silver_orchestrator,
}

_PURPOSES = {
    "table-profiler": "Perfila schema, nulos, cardinalidad y claves candidatas.",
    "quality-rule-advisor": "Propone reglas de calidad con evidencia.",
    "business-rule-validator": "Valida reglas contra schema y contrato.",
    "notebook-generator": "Genera blueprint de notebook gobernado.",
    "orchestrator": "Ejecuta el flujo completo en orden.",
}

_TOOLS = {
    "table-profiler": ["profile_selected_table"],
    "quality-rule-advisor": ["quality_rule_evidence"],
    "business-rule-validator": ["validate_business_rules"],
    "notebook-generator": ["build_notebook_blueprint"],
    "orchestrator": [
        "profile_selected_table",
        "quality_rule_evidence",
        "validate_business_rules",
        "build_notebook_blueprint",
    ],
}


@router.get("", response_model=list[AgentDescriptor])
def list_silver_agents() -> list[AgentDescriptor]:
    return [
        AgentDescriptor(
            name=name,
            purpose=_PURPOSES[name],
            model=(
                factory().model
                if hasattr(factory(), "model")
                else "sequential"
            ),
            deterministic_tools=_TOOLS[name],
        )
        for name, factory in _FACTORIES.items()
    ]


@router.post("/{agent_name}/run", response_model=AgentRunResponse)
async def run_silver_agent(
    agent_name: str,
    request: AgentRunRequest,
) -> AgentRunResponse:
    factory = _FACTORIES.get(agent_name)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agente Silver no encontrado: {agent_name}",
        )
    try:
        return await SilverAgentRunner().run(factory(), request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible ejecutar {agent_name}: {exc}",
        ) from exc
