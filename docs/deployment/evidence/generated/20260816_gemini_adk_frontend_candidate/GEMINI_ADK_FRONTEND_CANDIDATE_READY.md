# Gemini ADK Frontend Candidate - Evidence

## Status

**FUNCTIONAL AGENT FLOW CONFORME**

Date: 2026-08-16

Production was not modified by this validation. Package generation and Dataproc execution were intentionally not invoked.

## Candidate

- Frontend service: `business-rules-silver-ui-agents-test`
- Frontend URL: `https://business-rules-silver-ui-agents-test-mkqutd4koq-uc.a.run.app`
- Frontend revision: `business-rules-silver-ui-agents-test-00001-g9d`
- Backend service: `silver-refinement-agent-merge-test`
- Backend version: `8.2.0`
- Cloud Build: `fbf3c586-c278-4a90-a5c0-3c0f8bb82110`

## Access correction

The candidate build, image push and Cloud Run revision creation succeeded. Its initial smoke received HTTP 403 because the new frontend service lacked public invocation.

The following IAM binding was added:

- member: `allUsers`
- role: `roles/run.invoker`

After correction, the frontend returned `HTTP/2 200`.

## Live integration

The browser loaded the wizard and real backend data:

- Bronze and Silver datasets;
- source and target tables;
- the selected `cat_producto` schema;
- `producto_id`, `prima_base` and `bronze_fecha_ingesta`.

This confirms the candidate frontend-to-backend binding.

## Functional workflow

Created candidate workflow:

`workflow_d9814150f4d94eed971fd094b29aefbd`

### ADK table profiler

- agent: `silver_table_profiler`
- session: `silver-c9aed97a94644801b58b88c7f55e4d5e`
- status: `COMPLETED`
- table: `proyectopersonal-480420.seguros_bronce.cat_producto`
- row count: 13
- profiled columns: 12
- critical fields: 4
- candidate keys: 2
- candidate keys: `producto_id`, `bronze_registro_id`

The UI rendered canonical BigQuery evidence separately from the Gemini narrative output.

### ADK quality advisor

- agent: `silver_quality_rule_advisor`
- session: `silver-43cfa1bb07a947309e4117e997f810c7`
- status: `COMPLETED`
- evidence candidates: 16
- policy: every proposal requires human approval

The advisor proposed rules for nullability, uniqueness and low-cardinality domains. Rules requiring a value sample remained explicitly marked `NEEDS_VALUE_SAMPLE`.

### Human governance

No proposal was approved automatically.

Only these two critical rules were manually selected and confirmed:

1. `NOT_NULL(producto_id)`
2. `UNIQUE(producto_id)`

After confirmation:

- workflow version: 4
- workflow status: `IN_PROGRESS`
- backend message: rules generated and confirmed
- next stage: artifacts

## Safety boundary

The test stopped on the artifacts screen. It did not:

- generate or persist an artifact package;
- create an execution;
- submit Dataproc;
- change the production frontend;
- change the production backend.

## Conclusion

The frontend candidate, backend 8.2.0 integration, Gemini ADK profiler, quality advisor, canonical evidence contract and human approval gate are operational and **CONFORME** in the candidate environment.
