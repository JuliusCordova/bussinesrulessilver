# Post Execution BigQuery Result Validation

## Objective

`Ver resultado` must validate the BigQuery result produced by the Dataproc execution and expose the validation evidence to the UI.

A Silver execution is successful only when both conditions are true:

1. Dataproc Serverless finishes with `SUCCEEDED`.
2. BigQuery post-execution validation finishes `CONFORME`.

Dataproc `SUCCEEDED` alone is not a final business success state.

## Implemented Backend Contract

New endpoint:

`POST /executions/{execution_id}/result`

Response model:

`BigQueryValidationResponse`

Main fields:

- `status`: `CONFORME` or `NO_CONFORME`
- `conformant`: boolean
- `source_table`
- `target_table`
- `business_keys`
- `metric_column`
- `row_count`
- `distinct_business_key_count`
- `duplicate_count`
- `diff_count`
- `metric_sum`
- `checks[]`
- `execution`

## State Gate

`POST /executions/{execution_id}/sync-status` now runs BigQuery validation automatically when Dataproc reports `SUCCEEDED`.

Resulting state rules:

- Dataproc `RUNNING` -> execution `RUNNING`
- Dataproc `FAILED` -> execution `FAILED`
- Dataproc `SUCCEEDED` + BigQuery `CONFORME` -> execution `SUCCEEDED`
- Dataproc `SUCCEEDED` + BigQuery `NO_CONFORME` -> execution `FAILED`
- Dataproc `SUCCEEDED` + validation error -> execution `FAILED`

## Generic Table Support

Validation reads the artifact `SPECIFICATION_JSON` generated for the execution package.

It derives:

- source table from `source` or `source_project/source_dataset/source_table`
- target table from `target` or `target_project/target_dataset/target_table`
- business keys from `load_strategy.business_keys`
- metric column from explicit `metric_column` or first numeric non-key, non-traceability column in `columns`

Checks are generic:

1. target has rows;
2. no duplicate business keys;
3. row count equals distinct business keys;
4. source-vs-target diff by business key is empty when source is available;
5. metric sum comparison is included when a metric column is available.

If a table has no numeric metric, metric comparison is skipped while key and row validations still run.

## Frontend Contract

The API client now exposes:

`silverApi.getExecutionResult(executionId)`

`syncExecution` also accepts `validation_result` in its response.

## Pending UI Integration

The production UI can already receive the new result contract through `sync-status`, but `App.tsx` still needs a small UI patch to make the `Ver resultado` tile an explicit button and render a compact validation panel.

This was intentionally not rewritten through the GitHub connector because `App.tsx` is large and the connector updates files by full replacement. The safe next change is a local patch from Cloud Shell after pulling these backend/API commits.

## Next Planned Work

1. Add the explicit `Ver resultado` UI action and validation summary panel.
2. Add table profile driven configuration for business keys, watermark, metric and quality rules.
3. Add the Quality Rules Advisor agent.
4. Add the Agentic Code Generator once deterministic validation is stable.
