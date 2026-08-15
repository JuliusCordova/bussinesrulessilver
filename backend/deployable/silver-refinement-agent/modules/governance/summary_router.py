from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .summary_models import GovernanceSummaryResponse
from .summary_repository import GovernanceSummaryRepository
from .summary_service import GovernanceSummaryService


router = APIRouter(prefix="/governance", tags=["governance"])


def get_summary_service() -> GovernanceSummaryService:
    return GovernanceSummaryService(repository=GovernanceSummaryRepository())


@router.get("/summary", response_model=GovernanceSummaryResponse)
def get_governance_summary(
    service: GovernanceSummaryService = Depends(get_summary_service),
) -> GovernanceSummaryResponse:
    try:
        return service.get_summary()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible construir el resumen de gobierno: {exc}",
        ) from exc
