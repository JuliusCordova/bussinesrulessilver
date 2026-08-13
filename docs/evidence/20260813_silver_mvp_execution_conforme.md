# Silver MVP Execution Evidence - Bronze to Silver

## Executive Summary

The Business Rules Silver MVP was executed end-to-end against the `silver-refinement-agent` backend and BigQuery tables for `cat_producto`.

Final validated data result: **CONFORME** after controlled deduplication.

## Environment

- GCP project: `proyectopersonal-480420`
- Region: `us-central1`
- Backend service: `silver-refinement-agent`
- Backend URL: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`
- Frontend repository: `JuliusCordova/bussinesrulessilver`
- Source table: `seguros_bronce.cat_producto`
- Target table: `seguros_silver.cat_producto`

## Workflow Evidence

- Workflow ID: `workflow_48d79400907d44fabc468d0abc2dd86b`
- Spec ID: `spec_4e3c5c74da1d4413aae1b8b9d5a51efe`
- Execution ID: `exec_f51dfebbf93c4545ba452b29490810ab`
- Dataproc batch ID: `silver-exec-f51dfebbf93c4545ba452b29490810ab`
- Dataproc state: `SUCCEEDED`
- Frontend workflow state: `SUCCEEDED`

## Initial Post-Execution Validation

Initial validation showed Dataproc succeeded, but Silver data was not yet conforming because one duplicate row was present.

Observed result before cleanup:

| Metric | Value |
| --- | ---: |
| row_count | 14 |
| distinct_producto_id | 13 |
| sum_prima_base | 22070 |

Duplicate detected:

| producto_id | filas | suma_prima_base |
| --- | ---: | ---: |
| H3_PD_001 | 2 | 1360 |

Bronze vs Silver difference:

| producto_id | filas_bronze | filas_silver | suma_bronze | suma_silver | diff_filas | diff_suma |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H3_PD_001 | 1 | 2 | 680 | 1360 | 1 | 680 |

## Controlled Deduplication

A controlled BigQuery deduplication was executed on `seguros_silver.cat_producto`, preserving one record per `producto_id` and keeping the table partitioning and clustering aligned with the existing physical design.

Deduplication strategy:

```sql
CREATE OR REPLACE TABLE `proyectopersonal-480420.seguros_silver.cat_producto`
PARTITION BY DATE(bronze_fecha_ingesta)
CLUSTER BY producto_id, ramo_id, bronze_registro_id, bronze_carga_id AS
SELECT * EXCEPT(rn)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY producto_id
      ORDER BY bronze_fecha_ingesta DESC, bronze_registro_id DESC
    ) AS rn
  FROM `proyectopersonal-480420.seguros_silver.cat_producto`
)
WHERE rn = 1;
```

## Final Validation

Final BigQuery validation after deduplication:

| Metric | Value |
| --- | ---: |
| row_count | 13 |
| distinct_producto_id | 13 |
| sum_prima_base | 21390 |

Duplicate check result: **0 duplicate keys**.

## Conclusion

The MVP flow is validated end-to-end:

1. Real backend workflow creation.
2. Source confirmation.
3. Mapping recommendation.
4. Business rule generation and confirmation.
5. Specification and artifact package generation.
6. Execution creation.
7. Package validation.
8. Dataproc submission.
9. Dataproc status synchronization.
10. BigQuery post-execution validation.

Final status: **CONFORME**.

## Product Finding

The generated pipeline executed successfully but exposed an idempotency gap. A repeated or incremental execution can insert duplicated rows if the generated notebook/script behaves as append-only.

Required backlog item:

- Implement idempotent load semantics in generated Silver artifacts.
- Recommended behavior: use `MERGE` or deterministic deduplication by `business_key + watermark` before writing to the Silver target.
- MVP acceptance should require both conditions:
  - Dataproc execution state is `SUCCEEDED`.
  - Post-execution reconciliation is `CONFORME`.
