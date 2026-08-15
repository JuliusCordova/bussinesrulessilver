from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntelligentAssistantRequest(BaseModel):
    execution_id: str
    question: str = Field(min_length=3, max_length=2000)
    include_logs: bool = False
    use_gemini: bool = True


class AssistantGroundingReference(BaseModel):
    source: str
    reference: str
    detail: str


class IntelligentAssistantResponse(BaseModel):
    execution_id: str
    generated_at: datetime
    question: str
    answer: str
    provider: str
    model: str | None = None
    diagnosis_category: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    safe_to_automate: bool
    requires_human_review: bool
    grounding: list[AssistantGroundingReference] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
