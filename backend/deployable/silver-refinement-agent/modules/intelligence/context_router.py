from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.agentops.repository import AgentOpsRepository
from modules.agentops.service import AgentOpsService

from .context_models import IntelligenceExecutionContext
from .context_repository import IntelligenceContextRepository
from .context_service import IntelligenceContextService, IntelligenceExecutionNotFoundError


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def get_context_service() -> IntelligenceContextService:
    return IntelligenceContextService(
        repository=IntelligenceContextRepository(),
        agentops_service=AgentOpsService(repository=AgentOpsRepository()),
    )


@router.get(
    "/executions/{execution_id}/context",
    response_model=IntelligenceExecutionContext,
)
def get_execution_context(
    execution_id: str,
    include_logs: bool = Query(default=True),
    service: IntelligenceContextService = Depends(get_context_service),
) -> IntelligenceExecutionContext:
    try:
        return service.build(execution_id, include_logs=include_logs)
    except IntelligenceExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible construir el contexto inteligente: {exc}",
        ) from exc
