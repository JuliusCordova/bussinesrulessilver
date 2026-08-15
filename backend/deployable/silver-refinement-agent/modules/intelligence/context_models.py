from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContextSourceStatus(BaseModel):
    source: str
    status: str
    detail: str | None = None


class IntelligenceExecutionContext(BaseModel):
    execution_id: str
    generated_at: datetime
    completeness: str
    execution: dict[str, Any]
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    governance: dict[str, Any] = Field(default_factory=dict)
    logs: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    data_quality: dict[str, Any] | None = None
    profiling: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    platform_health: dict[str, Any] | None = None
    sources: list[ContextSourceStatus] = Field(default_factory=list)
