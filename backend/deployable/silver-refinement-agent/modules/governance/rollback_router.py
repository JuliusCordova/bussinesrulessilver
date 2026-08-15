from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .rollback_models import ArtifactRollbackHistoryResponse, ArtifactRollbackRequest, ArtifactRollbackResponse
from .rollback_repository import GovernanceRollbackRepository
from .rollback_service import GovernanceRollbackConflictError, GovernanceRollbackNotFoundError, GovernanceRollbackService

router = APIRouter(prefix="/governance", tags=["governance"])


def get_rollback_service() -> GovernanceRollbackService:
    return GovernanceRollbackService(repository=GovernanceRollbackRepository())


@router.get("/artifacts/{artifact_id}/rollbacks", response_model=ArtifactRollbackHistoryResponse)
def get_rollbacks(artifact_id: str, service: GovernanceRollbackService = Depends(get_rollback_service)) -> ArtifactRollbackHistoryResponse:
    try:
        return service.get_history(artifact_id)
    except GovernanceRollbackNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"No fue posible consultar rollbacks: {exc}") from exc


@router.post("/artifacts/{artifact_id}/rollback", response_model=ArtifactRollbackResponse)
def rollback_artifact(artifact_id: str, request: ArtifactRollbackRequest, service: GovernanceRollbackService = Depends(get_rollback_service)) -> ArtifactRollbackResponse:
    try:
        return service.rollback(
            artifact_id=artifact_id,
            rolled_back_by=request.rolled_back_by,
            comment=request.comment,
        )
    except GovernanceRollbackNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GovernanceRollbackConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"No fue posible ejecutar rollback: {exc}") from exc
