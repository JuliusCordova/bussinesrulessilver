from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArtifactReviewRequest(BaseModel):
    reviewed_by: str = Field(min_length=2, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)


class GovernanceArtifactItem(BaseModel):
    artifact_id: str
    spec_id: str
    mapping_version: int
    artifact_type: str
    artifact_version: int
    storage_uri: str | None = None
    content_hash: str | None = None
    generation_status: str
    validation_status: str
    generated_by: str
    generated_at: datetime
    is_current: bool
    decision: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    comment: str | None = None


class PendingArtifactReviewsResponse(BaseModel):
    total: int = Field(ge=0)
    artifacts: list[GovernanceArtifactItem]


class ArtifactDecisionResponse(BaseModel):
    artifact_id: str
    decision: str
    reviewed_by: str
    reviewed_at: datetime
    comment: str | None = None
    immutable: bool = True
