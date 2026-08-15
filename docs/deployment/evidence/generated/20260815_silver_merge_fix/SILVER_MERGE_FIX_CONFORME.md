# Silver Merge Fix - Evidence

## Executive Summary

The Business Rules Silver MVP was validated end-to-end using the patched Silver backend test service.

Final result: **CONFORME**

This validation is deterministic. No agentic code generation or RAG-based quality recommendation was used in this execution.

## Scope

Validated flow:

- Bronze source: `proyectopersonal-480420.seguros_bronce.cat_producto`
- Silver target: `proyectopersonal-480420.seguros_silver.cat_producto`
- Business key: `producto_id`
- Watermark column: `bronze_fecha_ingesta`
- Load strategy: `MERGE`
- Execution engine: Dataproc Serverless
- Frontend: Business Rules Silver wizard
- Backend: Silver Refinement backend test service

## Backend Test Service

- Service: `silver-refinement-agent-merge-test`
- URL: `https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app`
- Revision: `silver-refinement-agent-merge-test-00003-r85`
- Image tag: `us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent:merge-fix-cors-4618aac`
- Image digest: `sha256:7b511767b45127090e85c60b584dfa8fb0824907727f4e245be73b21bb021ec8`

Health check:

```json
{
  "status": "ok",
  "module": "silver-refinement",
  "version": "8.1.3"
}
```

## Fixes Included

### Backend

- Added deployable backend source under `backend/deployable/silver-refinement-agent`.
- Enabled CORS for browser-based frontend testing.
- Added deterministic MERGE support in `execution_artifact_generator.py`.

The implemented MERGE behavior is an idempotent overwrite with deterministic deduplication:

1. read existing target if present;
2. union existing target rows with current transformed rows;
3. deduplicate using `business_keys`;
4. order by `watermark_column` and optional `tie_breaker_column`;
5. write the deduplicated result using overwrite mode.

### Frontend

- Changed catalog workflow load strategy from `INCREMENTAL_WATERMARK` to `MERGE`.
- Sent backend-compatible quality rules using `rule_type`, `column_name`, `rule_parameters`, and severity fields.

## Runtime Evidence

- Workflow ID: `workflow_42b38535cfba4fda9e7dc5323a42ebdb`
- Spec ID: `spec_3d555e28be494c11945499fccdca4770`
- Execution ID: `exec_4a0d8124d98945ecbf4a5ffde1166e1c`
- Dataproc batch: `silver-exec-4a0d8124d98945ecbf4a5ffde1166e1c`
- Dataproc status: `SUCCEEDED`
- Backend execution status: `SUCCEEDED`

## BigQuery Validation

Validation query:

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT producto_id) AS distinct_producto_id,
  MIN(bronze_fecha_ingesta) AS min_bronze_fecha_ingesta,
  MAX(bronze_fecha_ingesta) AS max_bronze_fecha_ingesta,
  SUM(prima_base) AS sum_prima_base
FROM `proyectopersonal-480420.seguros_silver.cat_producto`;
```

Observed result:

| row_count | distinct_producto_id | min_bronze_fecha_ingesta | max_bronze_fecha_ingesta | sum_prima_base |
|---:|---:|---|---|---:|
| 13 | 13 | 2026-07-31 20:30:00 | 2026-08-01 20:30:00 | 21390 |

Duplicate validation:

```sql
SELECT
  producto_id,
  COUNT(*) AS filas,
  SUM(prima_base) AS suma_prima_base
FROM `proyectopersonal-480420.seguros_silver.cat_producto`
GROUP BY producto_id
HAVING COUNT(*) > 1;
```

Observed result:

No rows returned.

Bronze vs Silver validation:

No differences returned.

## Conclusion

The deterministic MVP flow is validated as **CONFORME**.

The patched backend test service successfully generated and executed a MERGE-based package without duplicating catalog rows.

## Not Included In This Validation

The following items remain planned but were not executed in this validation:

- Agentic code generator.
- Quality Rules Advisor Agent.
- RAG over corporate rules or historical notebook patterns.
- Production replacement of the original `silver-refinement-agent` service.
