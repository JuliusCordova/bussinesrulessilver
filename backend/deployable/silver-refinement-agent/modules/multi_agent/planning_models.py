from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlanningRequest(BaseModel):
    execution_id: str
    question: str = Field(min_length=3, max_length=2000)
    requested_agents: list[str] = Field(default_factory=list)
    max_agents: int = Field(default=5, ge=1, le=10)


class PlanStep(BaseModel):
    step_id: str
    stage: int = Field(ge=1)
    agent_id: str
    depends_on: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    condition: str = "ALWAYS"
    can_run_in_parallel: bool = False


class ExecutionPlan(BaseModel):
    plan_id: str
    execution_id: str
    generated_at: datetime
    strategy: str
    rationale: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    parallel_groups: list[list[str]] = Field(default_factory=list)
    max_parallelism: int = Field(ge=1)
    planning_time_ms: int = Field(ge=0)
    requires_human_review: bool = False
