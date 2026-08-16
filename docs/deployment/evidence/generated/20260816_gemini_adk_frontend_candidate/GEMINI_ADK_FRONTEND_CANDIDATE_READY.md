# Gemini ADK Candidate - End-to-End Evidence

## Status

**END-TO-END CONFORME**

Date: 2026-08-16

Production frontend and production backend were not modified. The execution used only the candidate services.

## Candidate

- Frontend: `business-rules-silver-ui-agents-test`
- Frontend URL: `https://business-rules-silver-ui-agents-test-mkqutd4koq-uc.a.run.app`
- Frontend revision: `business-rules-silver-ui-agents-test-00001-g9d`
- Backend: `silver-refinement-agent-merge-test`
- Backend version: `8.2.0`
- Final backend build: `2760098b-aefa-4b12-b645-6dad72428a3a`

## Workflow

- workflow: `workflow_d9814150f4d94eed971fd094b29aefbd`
- workflow version: `6`
- spec: `spec_30225060cb024f3e840f585660fb59c8`
- execution: `exec_5e196477105c4ca2b178cfd79e7cde19`
- batch: `silver-exec-5e196477105c4ca2b178cfd79e7cde19`

## Gemini ADK profiling

- agent: `silver_table_profiler`
- session: `silver-c9aed97a94644801b58b88c7f55e4d5e`
- status: `COMPLETED`
- source: `proyectopersonal-480420.seguros_bronce.cat_producto`
- rows: 13
- columns: 12
- critical fields: 4
- candidate keys: `producto_id`, `bronze_registro_id`

Metrics were rendered from canonical BigQuery evidence, independently of the Gemini narrative.

## Gemini ADK quality advisor

- agent: `silver_quality_rule_advisor`
- session: `silver-43cfa1bb07a947309e4117e997f810c7`
- status: `COMPLETED`
- evidence candidates: 16
- policy: every proposal requires human approval

No recommendation was applied automatically. Only these rules were manually approved:

1. `NOT_NULL(producto_id)`
2. `UNIQUE(producto_id)`

## Package

- mapping version: 1
- package version: 1
- load strategy: `MERGE`
- business key: `producto_id`
- watermark: `bronze_fecha_ingesta`
- validated files: 8
- package hash: `sha256:3ec061281fee1f50875a2fcdfc64f6489c8e15a843501c3ebeaaca6f6073f472`

The generated specification and PySpark script contain only the two manually approved quality rules.

## Physical design finding and correction

The first submit was safely blocked before Dataproc because the existing target had a compatible clustering superset:

- actual: `producto_id, ramo_id, bronze_registro_id, bronze_carga_id`
- governed minimum: `producto_id`

The materializer was corrected to accept an existing clustering layout only when the governed columns remain an ordered prefix. Missing or reordered governed clustering columns are still rejected.

- fix commit: `3540585`
- test commit: `75e9bb1`
- final candidate build status: `SUCCESS`

The same package was revalidated after deployment.

## Dataproc

- submission status: `QUEUED`
- runtime status: `RUNNING`
- terminal Dataproc state: `SUCCEEDED`
- operation: `projects/proyectopersonal-480420/regions/us-central1/operations/abf74cb9-ded9-310e-8fb7-24c171739085`

## Post-execution BigQuery validation

The backend only marked the execution `SUCCEEDED` after Dataproc and BigQuery validation were both conformant.

- status: `CONFORME`
- conformant: `true`
- target rows: 13
- distinct `producto_id`: 13
- duplicates: 0
- Bronze/Silver business-key differences: 0

Checks:

- `target_has_rows`: PASS
- `no_duplicate_business_keys`: PASS
- `row_count_equals_distinct_business_keys`: PASS
- `source_target_business_key_diff_empty`: PASS

The explicit **Ver resultado** action was also executed and returned the same conformant result.

## Conclusion

The candidate validates the complete governed flow:

1. real catalog selection;
2. Gemini ADK profiling;
3. evidence-based quality recommendations;
4. manual rule approval;
5. deterministic artifact generation;
6. package validation;
7. Dataproc execution;
8. mandatory post-execution BigQuery validation;
9. final `SUCCEEDED` only when both execution and validation are conformant.

Final result: **CONFORME**.
