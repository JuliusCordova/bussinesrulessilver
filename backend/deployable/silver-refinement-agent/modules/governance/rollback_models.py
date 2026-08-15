from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArtifactRollbackRequest(BaseModel):
    rolled_back_by: str = Field(min_length=2, max_length=200)
    comment: str = Field(min_length=3, max_length=2000)


class ArtifactRollbackResponse(BaseModel):
    rollback_id: str
    artifact_id: str
    spec_id: str
    artifact_version: int
    source_environment: str
    target_environment: str
    rolled_back_by: str
    rolled_back_at: datetime
    comment: str
    immutable: bool = True


class ArtifactRollbackHistoryResponse(BaseModel):
    artifact_id: str
    current_environment: str
    total: int = Field(ge=0)
    rollbacks: list[ArtifactRollbackResponse]
