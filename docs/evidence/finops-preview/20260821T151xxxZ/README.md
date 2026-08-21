# FinOps Governance Preview — deployment evidence

Date: 2026-08-21
Project: `proyectopersonal-480420`
Region: `us-central1`
Branch: `feat/finops-real-preview`

## Result

The isolated Governance Preview with real Silver FinOps telemetry was deployed successfully.

Cloud Run service:
- `business-rules-silver-governance-preview`

Revision:
- `business-rules-silver-governance-preview-00004-j6b`

Service URL reported by Cloud Run:
- `https://business-rules-silver-governance-preview-913797829604.us-central1.run.app`

Canonical preview URL reported by the deploy script:
- `https://business-rules-silver-governance-preview-mkqutd4koq-uc.a.run.app/`

Governance backend:
- `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`

FinOps candidate API:
- `https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app`

## Validation output

- `[1/6]` frontend preview validation: PASS
- `[2/6]` canonical backend / AgentOps contracts: PASS
- `[3/6]` real FinOps candidate endpoints: PASS
- `[4/6]` isolated Cloud Run deployment: SUCCESS
- `[5/6]` deployed frontend smoke test: PASS
- `[6/6]` preview ready: PASS

Final smoke message:

`PASS: preview interactivo servido con Gobierno + FinOps real`

## Data semantics

The preview uses real Business Rules Silver LLM telemetry for calls, tokens, governed runs and latency.

Cloud Billing Export has not been configured/discovered yet, therefore billed USD cost remains intentionally unavailable:
- `billing_cost_available = false`
- `cost_usd = null`

No synthetic or inferred USD cost is presented.

## Production impact

This validation concerns the isolated preview and candidate FinOps API. It does not constitute promotion of the FinOps changes to the production frontend/backend.
