from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ArtifactPromotionRequest(BaseModel):
    target_environment: str
    promoted_by: str = Field(min_length=2, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("target_environment")
    @classmethod
    def validate_target_environment(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"QA", "PROD"}:
            raise ValueError("target_environment debe ser QA o PROD")
        return normalized


class ArtifactPromotionResponse(BaseModel):
    promotion_id: str
    artifact_id: str
    spec_id: str
    artifact_version: int
    source_environment: str
    target_environment: str
    promoted_by: str
    promoted_at: datetime
    comment: str | None = None
    immutable: bool = True


class ArtifactPromotionHistoryResponse(BaseModel):
    artifact_id: str
    current_environment: str
    total: int = Field(ge=0)
    promotions: list[ArtifactPromotionResponse]
