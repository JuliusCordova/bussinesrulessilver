from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AlloyDBAvailabilityState(str, Enum):
    READY = "READY"
    STARTING = "STARTING"
    STOPPED = "STOPPED"
    UNAVAILABLE = "UNAVAILABLE"
    BYPASSED = "BYPASSED"


class AlloyDBAvailability(BaseModel):
    state: AlloyDBAvailabilityState
    ready: bool
    managed: bool
    retryable: bool
    reason: str
    retry_after_seconds: int | None = Field(default=None, ge=1)
    instance_state: str | None = None
    activation_policy: str | None = None
    request_id: str | None = None
    observed_at: datetime


class BusinessAvailabilityContext(BaseModel):
    operation: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=256)
    requested_by: str = Field(default="silver-refinement-agent", min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=256)
