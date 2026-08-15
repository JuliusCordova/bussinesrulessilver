from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .promotion_models import (
    ArtifactPromotionHistoryResponse,
    ArtifactPromotionRequest,
    ArtifactPromotionResponse,
)
from .promotion_repository import GovernancePromotionRepository
from .promotion_service import (
    GovernancePromotionConflictError,
    GovernancePromotionNotFoundError,
    GovernancePromotionService,
)


router = APIRouter(prefix="/governance", tags=["governance"])


def get_promotion_service() -> GovernancePromotionService:
    return GovernancePromotionService(repository=GovernancePromotionRepository())


@router.get(
    "/artifacts/{artifact_id}/promotions",
    response_model=ArtifactPromotionHistoryResponse,
)
def get_artifact_promotions(
    artifact_id: str,
    service: GovernancePromotionService = Depends(get_promotion_service),
) -> ArtifactPromotionHistoryResponse:
    try:
        return service.get_history(artifact_id)
    except GovernancePromotionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible consultar las promociones: {exc}",
        ) from exc


@router.post(
    "/artifacts/{artifact_id}/promote",
    response_model=ArtifactPromotionResponse,
)
def promote_artifact(
    artifact_id: str,
    request: ArtifactPromotionRequest,
    service: GovernancePromotionService = Depends(get_promotion_service),
) -> ArtifactPromotionResponse:
    try:
        return service.promote(
            artifact_id=artifact_id,
            target_environment=request.target_environment,
            promoted_by=request.promoted_by,
            comment=request.comment,
        )
    except GovernancePromotionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GovernancePromotionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible promover el artefacto: {exc}",
        ) from exc
