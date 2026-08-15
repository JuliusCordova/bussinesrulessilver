from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .models import (
    ArtifactDecisionResponse,
    ArtifactReviewRequest,
    PendingArtifactReviewsResponse,
)
from .repository import GovernanceRepository
from .service import (
    GovernanceArtifactNotFoundError,
    GovernanceDecisionConflictError,
    GovernanceService,
)


router = APIRouter(prefix="/governance", tags=["governance"])


def get_governance_service() -> GovernanceService:
    return GovernanceService(repository=GovernanceRepository())


@router.get(
    "/artifacts/pending",
    response_model=PendingArtifactReviewsResponse,
)
def list_pending_artifacts(
    limit: int = Query(default=100, ge=1, le=500),
    service: GovernanceService = Depends(get_governance_service),
) -> PendingArtifactReviewsResponse:
    try:
        return service.list_pending(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible listar artefactos pendientes: {exc}",
        ) from exc


@router.get(
    "/artifacts/{artifact_id}/decision",
    response_model=ArtifactDecisionResponse,
)
def get_artifact_decision(
    artifact_id: str,
    service: GovernanceService = Depends(get_governance_service),
) -> ArtifactDecisionResponse:
    try:
        return service.get_decision(artifact_id)
    except GovernanceArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible consultar la decisión: {exc}",
        ) from exc


@router.post(
    "/artifacts/{artifact_id}/approve",
    response_model=ArtifactDecisionResponse,
)
def approve_artifact(
    artifact_id: str,
    request: ArtifactReviewRequest,
    service: GovernanceService = Depends(get_governance_service),
) -> ArtifactDecisionResponse:
    return _decide(service, artifact_id, "APPROVED", request)


@router.post(
    "/artifacts/{artifact_id}/reject",
    response_model=ArtifactDecisionResponse,
)
def reject_artifact(
    artifact_id: str,
    request: ArtifactReviewRequest,
    service: GovernanceService = Depends(get_governance_service),
) -> ArtifactDecisionResponse:
    return _decide(service, artifact_id, "REJECTED", request)


def _decide(
    service: GovernanceService,
    artifact_id: str,
    decision: str,
    request: ArtifactReviewRequest,
) -> ArtifactDecisionResponse:
    try:
        return service.decide(
            artifact_id=artifact_id,
            decision=decision,
            reviewed_by=request.reviewed_by,
            comment=request.comment,
        )
    except GovernanceArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GovernanceDecisionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible registrar la decisión: {exc}",
        ) from exc
