# FinOps Product Attribution v1 — Preview deployment evidence

Date: 2026-08-21
Branch: `feat/finops-real-preview`
Product: `BUSINESS_RULES_SILVER`

## Candidate backend

Validated candidate endpoint:

`GET /agentops/finops/product-attribution?days=30`

Observed state before preview deployment:

- `product`: `BUSINESS_RULES_SILVER`
- `silver_llm_calls`: `27`
- `silver_governed_runs`: `15`
- `silver_tokens`: `127941`
- `billing_source_available`: `true`
- `billing_first_usage_at`: `2026-06-01T07:00:00Z`
- `billing_last_usage_at`: `2026-07-05T15:00:00Z`
- `temporal_overlap`: `false`
- `status`: `WAITING_TEMPORAL_OVERLAP`
- `attribution_semantics`: `ATRIBUCION_PENDIENTE_COBERTURA`
- `direct_cost_usd`: `null`
- `attributed_ai_cost_usd`: `null`
- `product_cost_usd`: `null`

Interpretation: Cloud Billing Export is real and materialized, but its current coverage does not overlap with Business Rules Silver AgentOps telemetry. Product-level cost attribution remains intentionally blocked; no synthetic or temporally mismatched USD is exposed.

## Preview deployment

Command:

```bash
cd ~/bussinesrulessilver
git pull --ff-only origin feat/finops-real-preview
bash scripts/deploy_governance_dashboard_preview.sh
```

Validation result:

1. PASS — shell interactivo, drill-downs y FinOps Billing-aware presentes
2. PASS — backend y contratos AgentOps accesibles
3. PASS — FinOps real; Billing materializado, cobertura reciente aún en backfill (`last_usage_at=2026-07-05T15:00:00Z`)
4. PASS — preview deployed to Cloud Run
5. PASS — preview interactivo servido con Gobierno + FinOps Billing-aware
6. PASS — preview listo

Cloud Run revision:

`business-rules-silver-governance-preview-00008-xwl`

Traffic:

`100%`

Preview URL:

`https://business-rules-silver-governance-preview-mkqutd4koq-uc.a.run.app/`

FinOps API candidate:

`https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app`

## Canonical conclusion

FinOps Product Attribution v1 is validated end-to-end in the isolated preview with governed semantics:

- `FACTURADO` only when Cloud Billing provides real cost for the requested period.
- `ATRIBUIDO` only when the attribution rule has valid evidence and temporal overlap.
- `NO DISPONIBLE / ATRIBUCION_PENDIENTE_COBERTURA` when evidence is insufficient.
- No synthetic cost values are permitted.

The next activation gate for product/agent/run cost is temporal overlap between Billing coverage and AgentOps telemetry.