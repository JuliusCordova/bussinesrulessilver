from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=128)
    source_dataset: str = Field(min_length=1, max_length=1024)
    source_table: str = Field(min_length=1, max_length=1024)
    target_dataset: str = Field(min_length=1, max_length=1024)
    target_table: str = Field(min_length=1, max_length=1024)
    business_keys: list[str] = Field(default_factory=list)
    watermark_column: str | None = None
    business_rules: list[dict[str, Any]] = Field(default_factory=list)
    approved_quality_rules: list[dict[str, Any]] = Field(default_factory=list)
    context: str | None = Field(default=None, max_length=8000)


class AgentRunResponse(BaseModel):
    agent_name: str
    session_id: str
    status: str
    output: str
    events: int


class AgentDescriptor(BaseModel):
    name: str
    purpose: str
    model: str
    deterministic_tools: list[str]
