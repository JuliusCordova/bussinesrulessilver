from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .finops_repository import SilverFinOpsRepository


router = APIRouter(prefix="/agentops/finops", tags=["agentops-finops"])


def get_finops_repository() -> SilverFinOpsRepository:
    return SilverFinOpsRepository()


@router.get("/summary")
def get_finops_summary(
    days: int = Query(default=30, ge=1, le=365),
    repository: SilverFinOpsRepository = Depends(get_finops_repository),
) -> dict:
    try:
        return repository.fetch_summary(days=days)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener resumen FinOps Silver: {exc}",
        ) from exc


@router.get("/daily")
def get_finops_daily(
    days: int = Query(default=30, ge=1, le=365),
    repository: SilverFinOpsRepository = Depends(get_finops_repository),
) -> dict:
    try:
        rows = repository.fetch_daily(days=days)
        return {
            "period_days": days,
            "series": rows,
            "billing_cost_available": False,
            "cost_usd": None,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener tendencia FinOps Silver: {exc}",
        ) from exc


@router.get("/agents")
def get_finops_agents(
    days: int = Query(default=30, ge=1, le=365),
    repository: SilverFinOpsRepository = Depends(get_finops_repository),
) -> dict:
    try:
        rows = repository.fetch_agents(days=days)
        return {
            "period_days": days,
            "agents": rows,
            "total": len(rows),
            "billing_cost_available": False,
            "cost_usd": None,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener consumo FinOps por agente: {exc}",
        ) from exc


@router.get("/runs")
def get_finops_runs(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    repository: SilverFinOpsRepository = Depends(get_finops_repository),
) -> dict:
    try:
        rows = repository.fetch_runs(days=days, limit=limit)
        return {
            "period_days": days,
            "runs": rows,
            "total": len(rows),
            "billing_cost_available": False,
            "cost_usd": None,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener consumo FinOps por run: {exc}",
        ) from exc
