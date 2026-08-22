from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.silver_agents.governance_repository import AgentGovernanceRepository
from modules.silver_execution.watermark_repository import WatermarkRepository

from .alerting import AgentOpsAlertService, AlertNotFoundError
from .models import (
    AgentOpsAlertsResponse,
    AgentOpsDashboardResponse,
    AgentOpsHealthResponse,
    AlertAcknowledgeRequest,
    AlertAcknowledgeResponse,
    ExecutionLogsResponse,
    ExecutionMetricsResponse,
    ExecutionTimelineResponse,
)
from .repository import AgentOpsRepository
from .quality_observability import (
    QualityEvidenceNotFoundError,
    QualityExecutionEvidence,
    QualityExecutionListResponse,
    QualityObservabilityRepository,
    QualitySummaryResponse,
)
from .service import (
    AgentOpsService,
    ExecutionLogsUnavailableError,
    ExecutionNotFoundError,
)


router = APIRouter(prefix="/agentops", tags=["agentops"])


def get_agentops_service() -> AgentOpsService:
    return AgentOpsService(
        repository=AgentOpsRepository(),
        watermark_repository=(
            WatermarkRepository() if os.getenv("ARTIFACT_BUCKET") else None
        ),
    )


def get_alert_service() -> AgentOpsAlertService:
    return AgentOpsAlertService()


def get_agent_governance_repository() -> AgentGovernanceRepository:
    return AgentGovernanceRepository()


def get_quality_observability_repository() -> QualityObservabilityRepository:
    return QualityObservabilityRepository()


@router.get("/governance/summary")
def get_agent_governance_summary(
    repository: AgentGovernanceRepository = Depends(
        get_agent_governance_repository
    ),
) -> dict:
    try:
        return repository.fetch_summary()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener gobierno agéntico: {exc}",
        ) from exc


@router.get("/governance/runs")
def get_agent_governance_runs(
    limit: int = Query(default=50, ge=1, le=200),
    repository: AgentGovernanceRepository = Depends(
        get_agent_governance_repository
    ),
) -> dict:
    try:
        runs = repository.fetch_runs(limit=limit)
        return {"runs": runs, "total": len(runs)}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener historial agéntico: {exc}",
        ) from exc


@router.get("/quality/summary", response_model=QualitySummaryResponse)
def get_quality_summary(
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualitySummaryResponse:
    try:
        return repository.fetch_summary()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener el resumen de calidad runtime: {exc}",
        ) from exc


@router.get("/quality/executions", response_model=QualityExecutionListResponse)
def get_quality_executions(
    limit: int = Query(default=50, ge=1, le=200),
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualityExecutionListResponse:
    try:
        return repository.list_latest(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener evidencia de calidad runtime: {exc}",
        ) from exc


@router.get(
    "/quality/executions/{execution_id}",
    response_model=QualityExecutionEvidence,
)
def get_quality_execution(
    execution_id: str,
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualityExecutionEvidence:
    try:
        return repository.get_latest(execution_id)
    except QualityEvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener la evidencia de calidad runtime: {exc}",
        ) from exc


@router.get("/dashboard", response_model=AgentOpsDashboardResponse)
def get_dashboard(
    service: AgentOpsService = Depends(get_agentops_service),
) -> AgentOpsDashboardResponse:
    try:
        return service.get_dashboard()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible construir el dashboard AgentOps: {exc}",
        ) from exc


@router.get("/health", response_model=AgentOpsHealthResponse)
def get_agentops_health(
    service: AgentOpsService = Depends(get_agentops_service),
) -> AgentOpsHealthResponse:
    try:
        return service.get_health()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible evaluar la salud de AgentOps: {exc}",
        ) from exc


@router.get("/alerts", response_model=AgentOpsAlertsResponse)
def get_alerts(
    limit: int = Query(default=100, ge=1, le=500),
    unread_only: bool = Query(default=False),
    service: AgentOpsAlertService = Depends(get_alert_service),
) -> AgentOpsAlertsResponse:
    try:
        return service.list_alerts(limit=limit, unread_only=unread_only)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener las alertas AgentOps: {exc}",
        ) from exc


@router.get("/alerts/unread", response_model=AgentOpsAlertsResponse)
def get_unread_alerts(
    limit: int = Query(default=100, ge=1, le=500),
    service: AgentOpsAlertService = Depends(get_alert_service),
) -> AgentOpsAlertsResponse:
    try:
        return service.list_alerts(limit=limit, unread_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener las alertas no atendidas: {exc}",
        ) from exc


@router.post(
    "/alerts/{alert_id}/ack",
    response_model=AlertAcknowledgeResponse,
)
def acknowledge_alert(
    alert_id: str,
    request: AlertAcknowledgeRequest,
    service: AgentOpsAlertService = Depends(get_alert_service),
) -> AlertAcknowledgeResponse:
    try:
        return service.acknowledge(alert_id, request.acknowledged_by)
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible reconocer la alerta: {exc}",
        ) from exc


@router.get("/executions", response_model=ExecutionTimelineResponse)
def get_execution_timeline(
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    spec_id: str | None = Query(default=None),
    service: AgentOpsService = Depends(get_agentops_service),
) -> ExecutionTimelineResponse:
    try:
        return service.get_execution_timeline(
            limit=limit,
            offset=offset,
            status=status_filter.upper() if status_filter else None,
            spec_id=spec_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener la línea de tiempo de ejecuciones: {exc}",
        ) from exc


@router.get(
    "/executions/{execution_id}/logs",
    response_model=ExecutionLogsResponse,
)
def get_execution_logs(
    execution_id: str,
    tail_lines: int = Query(default=200, ge=1, le=2000),
    service: AgentOpsService = Depends(get_agentops_service),
) -> ExecutionLogsResponse:
    try:
        return service.get_execution_logs(execution_id, tail_lines=tail_lines)
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExecutionLogsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener los logs de la ejecución: {exc}",
        ) from exc


@router.post(
    "/executions/{execution_id}/metrics/sync",
    response_model=ExecutionMetricsResponse,
)
def sync_execution_metrics(
    execution_id: str,
    service: AgentOpsService = Depends(get_agentops_service),
) -> ExecutionMetricsResponse:
    try:
        return service.sync_execution_metrics(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExecutionLogsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible sincronizar las métricas de la ejecución: {exc}",
        ) from exc
