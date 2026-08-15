from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser numérico") from exc
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un entero") from exc
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


@dataclass(frozen=True)
class AlloyDBAvailabilitySettings:
    enabled: bool
    controller_url: str | None
    audience: str | None
    timeout_seconds: float
    retry_after_seconds: int


@lru_cache
def get_alloydb_availability_settings() -> AlloyDBAvailabilitySettings:
    enabled = _as_bool("ALLOYDB_ON_DEMAND_ENABLED", False)
    controller_url = (os.getenv("ALLOYDB_POWER_CONTROLLER_URL") or "").strip() or None
    audience = (
        (os.getenv("ALLOYDB_POWER_CONTROLLER_AUDIENCE") or "").strip()
        or controller_url
    )

    if enabled and not controller_url:
        raise ValueError(
            "ALLOYDB_POWER_CONTROLLER_URL es obligatorio cuando "
            "ALLOYDB_ON_DEMAND_ENABLED=true"
        )

    return AlloyDBAvailabilitySettings(
        enabled=enabled,
        controller_url=controller_url,
        audience=audience,
        timeout_seconds=_as_float("ALLOYDB_POWER_CONTROLLER_TIMEOUT_SECONDS", 10.0),
        retry_after_seconds=_as_int("ALLOYDB_START_RETRY_AFTER_SECONDS", 15),
    )


def reset_alloydb_availability_settings() -> None:
    get_alloydb_availability_settings.cache_clear()
