from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .context_router import get_context_service
from .context_service import IntelligenceContextService, IntelligenceExecutionNotFoundError
from .diagnosis_engine import IntelligentDiagnosisEngine
from .remediation_engine import IntelligentRemediationEngine
from .remediation_models import RemediationPlan


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def get_diagnosis_engine() -> IntelligentDiagnosisEngine:
    return IntelligentDiagnosisEngine()


def get_remediation_engine() -> IntelligentRemediationEngine:
    return IntelligentRemediationEngine()


@router.get(
    "/executions/{execution_id}/remediation-plan",
    response_model=RemediationPlan,
)
def get_remediation_plan(
    execution_id: str,
    include_logs: bool = Query(default=False),
    context_service: IntelligenceContextService = Depends(get_context_service),
    diagnosis_engine: IntelligentDiagnosisEngine = Depends(get_diagnosis_engine),
    remediation_engine: IntelligentRemediationEngine = Depends(get_remediation_engine),
) -> RemediationPlan:
    try:
        context = context_service.build(execution_id, include_logs=include_logs)
        diagnosis = diagnosis_engine.diagnose(context)
        return remediation_engine.build(diagnosis)
    except IntelligenceExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible construir el plan de remediación: {exc}",
        ) from exc
