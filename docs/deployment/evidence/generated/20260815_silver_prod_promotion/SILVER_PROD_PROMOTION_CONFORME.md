# Silver Production Promotion - Evidence

## Executive Summary

The Business Rules Silver MVP was promoted to the production Cloud Run service and validated end-to-end.

Final result: **CONFORME**

This validation is deterministic. No agentic code generation, RAG-based rule recommendation, or adaptive runtime decisioning was used in this execution.

## Production Backend

- Service: `silver-refinement-agent`
- URL: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`
- Revision: `silver-refinement-agent-mergefix-1786834335`
- Traffic: `100%`
- Image digest: `sha256:7b511767b45127090e85c60b584dfa8fb0824907727f4e245be73b21bb021ec8`
- Image source: `us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent@sha256:7b511767b45127090e85c60b584dfa8fb0824907727f4e245be73b21bb021ec8`

## Production Readiness Checks

### Health

`GET /health` returned:

```json
{
  "status": "ok",
  "module": "silver-refinement",
  "version": "8.1.3"
}
```

### CORS

`OPTIONS /silver-workflows` against the production URL returned:

- `HTTP/2 200`
- `access-control-allow-origin: *`
- `access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT`
- `access-control-allow-headers: content-type`

## Production Workflow Execution

The frontend completed the full Bronze to Silver workflow against production.

- Workflow ID: `workflow_326cf489d1f545d084d5de974e67edf7`
- Spec ID: `spec_5691fb1b2a8c4b018b3a520cb502c489`
- Execution ID: `exec_9f3ca639f20045d4a0342c58023b0177`
- Dataproc batch: `silver-exec-9f3ca639f20045d4a0342c58023b0177`
- Dataproc state: `SUCCEEDED`
- Frontend state: `SUCCEEDED`

## Scope Validated

- Source table: `proyectopersonal-480420.seguros_bronce.cat_producto`
- Target table: `proyectopersonal-480420.seguros_silver.cat_producto`
- Business key: `producto_id`
- Watermark column: `bronze_fecha_ingesta`
- Load strategy: `MERGE`
- Execution engine: Dataproc Serverless
- Frontend: Business Rules Silver wizard
- Backend: production `silver-refinement-agent`

## BigQuery Validation

### Silver Profile

```text
row_count: 13
distinct_producto_id: 13
min_bronze_fecha_ingesta: 2026-07-31 20:30:00
max_bronze_fecha_ingesta: 2026-08-01 20:30:00
sum_prima_base: 21390
```

### Duplicate Check

Query grouping by `producto_id` with `HAVING COUNT(*) > 1` returned no rows.

### Bronze vs Silver Diff

Bronze vs Silver comparison by `producto_id`, row count, and `SUM(prima_base)` returned no rows.

## Acceptance Criteria

| Criterion | Result |
| --- | --- |
| Production backend responds to health check | PASS |
| Production CORS preflight succeeds | PASS |
| Frontend can call production backend | PASS |
| Workflow reaches Dataproc execution | PASS |
| Dataproc execution completes | PASS |
| Silver row count equals expected 13 | PASS |
| Silver distinct `producto_id` equals expected 13 | PASS |
| Silver `SUM(prima_base)` equals expected 21390 | PASS |
| No duplicate `producto_id` in Silver | PASS |
| Bronze vs Silver diff is empty | PASS |

## Technical Notes

The production issue before promotion was caused by Cloud Run traffic still pointing to an old revision using digest `sha256:1ece1c196b3d52cb41dfb78e64f5ee1502eeee905167622e6cbdc85dd87566f3`.

The corrected promotion forced a new revision from the validated digest and routed 100% of traffic to:

`silver-refinement-agent-mergefix-1786834335`

## Status

Sprint 1 deterministic MVP is production validated.

Next planned work remains outside this deterministic MVP:

1. Agentic code generation from approved Silver spec.
2. Agentic quality rule recommendation from BigQuery profiling.
3. Optional RAG only if corporate standards, historical patterns, or approved notebooks need retrieval.
