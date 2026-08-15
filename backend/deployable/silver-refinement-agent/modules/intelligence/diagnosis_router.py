from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .context_router import get_context_service
from .context_service import IntelligenceContextService, IntelligenceExecutionNotFoundError
from .diagnosis_engine import IntelligentDiagnosisEngine
from .diagnosis_models import IntelligenceExecutionDiagnosis


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def get_diagnosis_engine() -> IntelligentDiagnosisEngine:
    return IntelligentDiagnosisEngine()


@router.get(
    "/executions/{execution_id}/diagnosis",
    response_model=IntelligenceExecutionDiagnosis,
)
def get_execution_diagnosis(
    execution_id: str,
    include_logs: bool = Query(default=False),
    context_service: IntelligenceContextService = Depends(get_context_service),
    engine: IntelligentDiagnosisEngine = Depends(get_diagnosis_engine),
) -> IntelligenceExecutionDiagnosis:
    try:
        context = context_service.build(execution_id, include_logs=include_logs)
        return engine.diagnose(context)
    except IntelligenceExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible diagnosticar la ejecución: {exc}",
        ) from exc
