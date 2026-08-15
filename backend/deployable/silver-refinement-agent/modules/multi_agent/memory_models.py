from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemorySessionCreate(BaseModel):
    session_id: str | None = Field(default=None, min_length=3, max_length=160)
    execution_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemorySession(BaseModel):
    session_id: str
    execution_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    user_id: str | None = None
    status: str = "ACTIVE"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MemoryEventCreate(BaseModel):
    session_id: str
    execution_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    agent_id: str | None = None
    memory_type: str = "EPISODIC"
    content: str = Field(min_length=1, max_length=12000)
    importance_score: float = Field(default=0.5, ge=0, le=1)
    confidence_score: float = Field(default=1.0, ge=0, le=1)
    is_shared: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None


class MemoryRecord(BaseModel):
    memory_id: str
    session_id: str
    execution_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    agent_id: str | None = None
    memory_type: str
    content: str
    importance_score: float
    confidence_score: float = 1.0
    is_shared: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime | None = None


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    session_id: str | None = None
    execution_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    pipeline_id: str | None = None
    agent_id: str | None = None
    memory_types: list[str] = Field(default_factory=list)
    shared_only: bool | None = None
    limit: int = Field(default=10, ge=1, le=50)


class MemorySearchHit(BaseModel):
    memory: MemoryRecord
    score: float = Field(ge=0, le=1)
    match_type: str


class MemorySearchResponse(BaseModel):
    query: str
    hits: list[MemorySearchHit] = Field(default_factory=list)
    provider: str
    vector_index_ready: bool
