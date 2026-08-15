from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .audit_models import GovernanceAuditTrailResponse
from .audit_repository import GovernanceAuditRepository
from .audit_service import GovernanceAuditNotFoundError, GovernanceAuditService


router = APIRouter(prefix="/governance", tags=["governance"])


def get_audit_service() -> GovernanceAuditService:
    return GovernanceAuditService(repository=GovernanceAuditRepository())


@router.get(
    "/artifacts/{artifact_id}/audit-trail",
    response_model=GovernanceAuditTrailResponse,
)
def get_artifact_audit_trail(
    artifact_id: str,
    service: GovernanceAuditService = Depends(get_audit_service),
) -> GovernanceAuditTrailResponse:
    try:
        return service.get_trail(artifact_id)
    except GovernanceAuditNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible consultar el audit trail: {exc}",
        ) from exc
