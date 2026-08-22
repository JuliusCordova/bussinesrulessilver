from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from google.adk.agents import BaseAgent

from .agents import (
    build_business_rule_validator_agent,
    build_mapping_advisor_agent,
    build_notebook_generator_agent,
    build_quality_rule_advisor_agent,
    build_silver_orchestrator,
    build_table_profiler_agent,
)
from .governance_repository import AgentGovernanceRepository
from .models import AgentDescriptor, AgentRunRequest, AgentRunResponse
from .profile_report import ProfileReportService
from .service import SilverAgentRunner
from .tools import (
    profile_selected_table,
    quality_rule_evidence,
    recommend_column_mappings,
    validate_derived_nl_mapping_proposal,
    validate_quality_nl_rule_proposal,
)


router = APIRouter(prefix="/silver-agents", tags=["silver-agents"])

_FACTORIES: dict[str, Callable[[], BaseAgent]] = {
    "table-profiler": build_table_profiler_agent,
    "mapping-advisor": build_mapping_advisor_agent,
    "quality-rule-advisor": build_quality_rule_advisor_agent,
    "business-rule-validator": build_business_rule_validator_agent,
    "notebook-generator": build_notebook_generator_agent,
    "orchestrator": build_silver_orchestrator,
}

_PURPOSES = {
    "table-profiler": "Perfila schema, nulos, cardinalidad y claves candidatas.",
    "mapping-advisor": "Propone mapping editable desde schema y perfil reales.",
    "quality-rule-advisor": "Propone reglas de calidad con evidencia.",
    "business-rule-validator": "Valida reglas contra schema y contrato.",
    "notebook-generator": "Genera blueprint de notebook gobernado.",
    "orchestrator": "Ejecuta el flujo completo en orden.",
}

_TOOLS = {
    "table-profiler": ["profile_selected_table"],
    "mapping-advisor": ["profile_selected_table", "recommend_column_mappings", "validate_derived_nl_mapping_proposal"],
    "quality-rule-advisor": [
        "profile_selected_table",
        "quality_rule_evidence",
        "validate_quality_nl_rule_proposal",
    ],
    "business-rule-validator": [
        "profile_selected_table",
        "validate_business_rules",
    ],
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
    descriptors: list[AgentDescriptor] = []
    for name, factory in _FACTORIES.items():
        agent = factory()
        descriptors.append(
            AgentDescriptor(
                name=name,
                purpose=_PURPOSES[name],
                model=str(getattr(agent, "model", "sequential")),
                deterministic_tools=_TOOLS[name],
            )
        )
    return descriptors


@router.post("/table-profiler/report")
def build_table_profile_report(request: AgentRunRequest) -> Response:
    """Return a governed PDF built from a fresh canonical BigQuery profile."""
    try:
        profile = profile_selected_table(
            request.project_id,
            request.source_dataset,
            request.source_table,
        )
        content = ProfileReportService().build(profile)
        filename = f"profile-{request.source_dataset}-{request.source_table}.pdf"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible generar el informe de perfilamiento: {exc}",
        ) from exc


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
    run_id = f"agent-run-{uuid.uuid4().hex}"
    started_at = datetime.now(timezone.utc)
    governance = AgentGovernanceRepository()
    source_table = (
        f"{request.project_id}.{request.source_dataset}.{request.source_table}"
    )
    target_table = (
        f"{request.target_project_id or request.project_id}."
        f"{request.target_dataset}.{request.target_table}"
    )
    try:
        result = await SilverAgentRunner().run(
            factory(),
            request,
            user_id=request.requested_by or "business-rules-silver",
            trace_id=run_id,
        )
        if agent_name in {"table-profiler", "mapping-advisor", "quality-rule-advisor"}:
            profile = profile_selected_table(
                request.project_id,
                request.source_dataset,
                request.source_table,
            )
            if agent_name == "table-profiler":
                result.evidence = profile
            elif agent_name == "mapping-advisor":
                context = (request.context or "").strip()
                if context.startswith("DERIVED_NL:"):
                    natural_rule = context.split(":", 1)[1].strip()
                    cleaned = result.output.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.replace("```json", "", 1).replace("```", "", 1).strip()
                    parsed = json.loads(cleaned)
                    if not isinstance(parsed, dict):
                        raise ValueError("El mapping-advisor no devolvió un objeto JSON DERIVED_NL")
                    candidate = parsed.get("proposal") if isinstance(parsed.get("proposal"), dict) else parsed
                    result.evidence = validate_derived_nl_mapping_proposal(
                        json.dumps(request.columns, ensure_ascii=False),
                        natural_rule,
                        json.dumps(candidate, ensure_ascii=False),
                    )
                else:
                    result.evidence = recommend_column_mappings(
                        json.dumps(request.columns, ensure_ascii=False),
                        json.dumps(profile, ensure_ascii=False),
                    )
            else:
                context = (request.context or "").strip()
                if context.startswith("QUALITY_NL:"):
                    natural_rule = context.split(":", 1)[1].strip()
                    cleaned = result.output.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.replace("```json", "", 1).replace("```", "", 1).strip()
                    parsed = json.loads(cleaned)
                    if not isinstance(parsed, dict):
                        raise ValueError("El quality-rule-advisor no devolvió un objeto JSON QUALITY_NL")
                    candidate = parsed.get("proposal") if isinstance(parsed.get("proposal"), dict) else parsed
                    result.evidence = validate_quality_nl_rule_proposal(
                        json.dumps(request.columns, ensure_ascii=False),
                        natural_rule,
                        json.dumps(candidate, ensure_ascii=False),
                    )
                else:
                    result.evidence = quality_rule_evidence(
                        json.dumps(profile, ensure_ascii=False),
                        json.dumps(request.business_keys, ensure_ascii=False),
                    )
        finished_at = datetime.now(timezone.utc)
        governance.save_run(
            run_id=run_id,
            agent_name=agent_name,
            session_id=result.session_id,
            status=result.status,
            requested_by=request.requested_by,
            source_table=source_table,
            target_table=target_table,
            event_count=result.events,
            duration_ms=max(
                int((finished_at - started_at).total_seconds() * 1000),
                0,
            ),
            started_at=started_at,
            finished_at=finished_at,
            evidence=result.evidence,
        )
        return result
    except ValueError as exc:
        finished_at = datetime.now(timezone.utc)
        governance.save_run(
            run_id=run_id,
            agent_name=agent_name,
            session_id=None,
            status="FAILED",
            requested_by=request.requested_by,
            source_table=source_table,
            target_table=target_table,
            event_count=0,
            duration_ms=max(
                int((finished_at - started_at).total_seconds() * 1000),
                0,
            ),
            started_at=started_at,
            finished_at=finished_at,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        try:
            governance.save_run(
                run_id=run_id,
                agent_name=agent_name,
                session_id=None,
                status="FAILED",
                requested_by=request.requested_by,
                source_table=source_table,
                target_table=target_table,
                event_count=0,
                duration_ms=max(
                    int((finished_at - started_at).total_seconds() * 1000),
                    0,
                ),
                started_at=started_at,
                finished_at=finished_at,
                error_message=str(exc),
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible ejecutar {agent_name}: {exc}",
        ) from exc
