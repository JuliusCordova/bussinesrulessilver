from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .planning_engine import PlanningEngine
from .planning_models import ExecutionPlan, PlanningRequest


router = APIRouter(prefix="/agentops", tags=["multi-agent-planning"])


def get_planning_engine() -> PlanningEngine:
    return PlanningEngine()


@router.post("/planner/plan", response_model=ExecutionPlan)
def build_execution_plan(
    request: PlanningRequest,
    engine: PlanningEngine = Depends(get_planning_engine),
) -> ExecutionPlan:
    try:
        return engine.build(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible construir el plan multiagente: {exc}",
        ) from exc
