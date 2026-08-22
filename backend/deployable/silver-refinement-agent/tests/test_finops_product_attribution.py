from __future__ import annotations

from modules.agentops.finops_product_attribution import PRODUCT_CODE
from modules.agentops.finops_router import get_finops_product_attribution


class FakePendingProductRepository:
    def fetch_product_attribution(self, *, days: int):
        return {
            "product": PRODUCT_CODE,
            "period_days": days,
            "billing_source_available": True,
            "billing_first_usage_at": "2026-06-01T07:00:00Z",
            "billing_last_usage_at": "2026-07-04T12:00:00Z",
            "silver_first_call_at": "2026-08-21T14:53:50Z",
            "silver_last_call_at": "2026-08-21T19:53:34Z",
            "silver_llm_calls": 23,
            "silver_tokens": 111401,
            "temporal_overlap": False,
            "status": "WAITING_TEMPORAL_OVERLAP",
            "direct_cost_usd": None,
            "attributed_ai_cost_usd": None,
            "product_cost_usd": None,
            "attribution_coverage_pct": 0.0,
            "attribution_semantics": "ATRIBUCION_PENDIENTE_COBERTURA",
            "confidence": "PENDING",
        }


class FakeDirectProductRepository:
    def fetch_product_attribution(self, *, days: int):
        return {
            "product": PRODUCT_CODE,
            "period_days": days,
            "billing_source_available": True,
            "temporal_overlap": True,
            "status": "DIRECT_ATTRIBUTION_AVAILABLE",
            "direct_resources": [
                {
                    "service": "Cloud Run",
                    "resource_name": "silver-refinement-agent",
                    "cost_usd": 0.23,
                }
            ],
            "direct_cost_usd": 0.23,
            "attributed_ai_cost_usd": None,
            "product_cost_usd": 0.23,
            "attribution_semantics": "ATRIBUIDO_DIRECTO_PARCIAL",
            "confidence": "HIGH_DIRECT_ONLY",
            "ai_attribution_status": "DENOMINATOR_VALIDATION_PENDING",
        }


def test_product_attribution_waits_for_temporal_overlap() -> None:
    result = get_finops_product_attribution(days=30, repository=FakePendingProductRepository())
    assert result["product"] == "BUSINESS_RULES_SILVER"
    assert result["temporal_overlap"] is False
    assert result["status"] == "WAITING_TEMPORAL_OVERLAP"
    assert result["product_cost_usd"] is None
    assert result["attribution_semantics"] == "ATRIBUCION_PENDIENTE_COBERTURA"


def test_product_attribution_exposes_only_direct_cost_when_ai_denominator_is_pending() -> None:
    result = get_finops_product_attribution(days=30, repository=FakeDirectProductRepository())
    assert result["temporal_overlap"] is True
    assert result["direct_cost_usd"] == 0.23
    assert result["product_cost_usd"] == 0.23
    assert result["attributed_ai_cost_usd"] is None
    assert result["attribution_semantics"] == "ATRIBUIDO_DIRECTO_PARCIAL"
    assert result["confidence"] == "HIGH_DIRECT_ONLY"
