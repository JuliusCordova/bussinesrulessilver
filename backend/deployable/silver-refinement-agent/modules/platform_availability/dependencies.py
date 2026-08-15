from __future__ import annotations

from functools import lru_cache

from .power_controller_client import AlloyDBPowerControllerClient
from .service import AlloyDBAvailabilityService
from .settings import get_alloydb_availability_settings


@lru_cache
def get_alloydb_availability_service() -> AlloyDBAvailabilityService:
    settings = get_alloydb_availability_settings()
    client = (
        AlloyDBPowerControllerClient(settings=settings)
        if settings.enabled
        else None
    )
    return AlloyDBAvailabilityService(settings=settings, client=client)


def reset_alloydb_availability_dependencies() -> None:
    get_alloydb_availability_service.cache_clear()
