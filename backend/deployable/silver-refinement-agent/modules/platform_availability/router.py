from __future__ import annotations

from fastapi import APIRouter, Depends

from .dependencies import get_alloydb_availability_service
from .models import AlloyDBAvailability
from .service import AlloyDBAvailabilityService


router = APIRouter(prefix="/platform/availability", tags=["platform-availability"])


@router.get("/alloydb", response_model=AlloyDBAvailability)
def get_alloydb_availability(
    service: AlloyDBAvailabilityService = Depends(get_alloydb_availability_service),
) -> AlloyDBAvailability:
    """Read-only state projection. This endpoint never starts AlloyDB."""

    return service.observe()
