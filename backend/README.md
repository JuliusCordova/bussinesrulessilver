# Backend Canonical Checkpoint - Business Rules Silver / F2

## Purpose

This folder is the canonical backend checkpoint for the Business Rules Silver workstream.

It exists to prevent repeating backend discovery, mixing services, or reopening decisions that were already validated.

## Canonical Date

- Canonical F2 state: `2026-08-12`
- Silver MVP execution evidence: `2026-08-13`

## Service Boundary

There are two different backend surfaces. They must not be confused.

### 1. F2 Reconciliation Backend

Purpose: validate Bronze vs Silver reconciliation and persist a `CONFORME` result.

- Service: `jarvis-reconciliation-agent`
- Canonical API URL: `https://jarvis-reconciliation-agent-mkqutd4koq-uc.a.run.app`
- Connection: `CONN_BQ_DEMO`
- Project: `proyectopersonal-480420`
- Region: `us-central1`
- Canonical user: `julio.cordova@gmail.com`

Supported F2 flow:

```text
create draft -> validate -> confirm -> execute -> result
```

Confirmed F2 contract:

```text
POST /reconciliation/configure/draft
POST /reconciliation/configure/validate/{draft_id}
POST /reconciliation/configure/confirm/{draft_id}
POST /reconciliation/execute
GET  /reconciliation/result/{execution_id}
GET  /reconciliation/latest/{reconciliation_id}
```

Invalid/deprecated route:

```text
/reconciliation/drafts
```

### 2. Silver Refinement Backend

Purpose: create and operate the governed Bronze to Silver workflow, including mapping, rules, artifact generation, execution creation, package validation, Dataproc submit, and status sync.

- Service: `silver-refinement-agent`
- API URL: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`
- Health response observed:

```json
{
  "status": "ok",
  "module": "silver-refinement",
  "version": "8.1.3"
}
```

Core Silver endpoints discovered through OpenAPI:

```text
GET  /health
GET  /silver-workflows/health
POST /silver-workflows
GET  /silver-workflows
GET  /silver-workflows/{workflow_id}
POST /silver-workflows/{workflow_id}/confirm-source
POST /silver-workflows/{workflow_id}/mapping-recommendations
POST /silver-workflows/{workflow_id}/business-rules/generate
PUT  /silver-workflows/{workflow_id}/business-rules/draft
POST /silver-workflows/{workflow_id}/business-rules/confirm
POST /silver-workflows/{workflow_id}/quality-review
POST /silver-workflows/{workflow_id}/specification
POST /silver-refinement/specs/{spec_id}/artifacts/generate
POST /executions
POST /executions/{execution_id}/validate-package
POST /executions/{execution_id}/submit
POST /executions/{execution_id}/sync-status
```

Catalog endpoints:

```text
GET /silver-workflows/catalog/projects/{project_id}/datasets
GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables
GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}
```

## Canonical BigQuery Pair

```text
Source: proyectopersonal-480420.seguros_bronce.cat_producto
Target: proyectopersonal-480420.seguros_silver.cat_producto
Location: US
Type: native BigQuery tables
```

Canonical fields:

```text
business_key = ["producto_id"]
date_column = "bronze_fecha_ingesta"
watermark = "bronze_fecha_ingesta"
sum_columns = ["prima_base"]
metric = "prima_base"
```

Physical design observed for Silver target:

```text
PARTITION BY DATE(bronze_fecha_ingesta)
CLUSTER BY producto_id, ramo_id, bronze_registro_id, bronze_carga_id
```

## F2 Canonical Configuration

```text
process_name=Reconciliación catálogo de productos
domain_name=Seguros

source_project=proyectopersonal-480420
source_dataset=seguros_bronce
source_table=cat_producto
source_filter=NULL

target_project=proyectopersonal-480420
target_dataset=seguros_silver
target_table=cat_producto
target_filter=NULL

business_key=["producto_id"]
date_column="bronze_fecha_ingesta"
sum_columns=["prima_base"]

row_tolerance=0
amount_tolerance=0
severity_level=CRITICO
active_flag=TRUE
```

Filter decision:

```text
Use empty/null filters so the executor builds WHERE 1=1.
Do not use bronze_fecha_ingesta = @business_date for this catalog, because it can limit the comparison incorrectly.
```

Date-column limitation:

```text
bronze_fecha_ingesta is a technical ingestion timestamp, not a business date.
It is configured only because the reconciler requires date_column and computes min/max dates.
Product limitation: the reconciler requires a date column even for master/catalog tables.
```

## Canonical Expected Result

```text
SOURCE_ROWS=13
TARGET_ROWS=13
ROW_DIFF=0
SOURCE_SUM_prima_base=21390
TARGET_SUM_prima_base=21390
AMOUNT_DIFF=0
OVERALL_STATUS=CONFORME
```

## Evidence Already Validated - Do Not Repeat

These items were already validated and should not be rediscovered unless code or environment changes:

```text
Rows by metadata: 13 / 13
Columns: 12 / 12
Exact schema match: YES
Queried row count: 13 / 13
Distinct producto_id: 13 / 13
Null producto_id: 0 / 0
Null prima_base: 0 / 0
SUM(prima_base): 21390 / 21390
Preflight aggregate: PASS
```

## Silver MVP Execution Evidence

The Silver MVP was executed end-to-end through the frontend and real backend.

Observed successful execution:

```text
Workflow state: SUCCEEDED
Dataproc state: SUCCEEDED
Dataproc batch: silver-exec-f51dfebbf93c4545ba452b29490810ab
```

Final BigQuery validation after controlled deduplication:

```text
row_count=13
distinct_producto_id=13
sum_prima_base=21390
duplicate_keys=0
```

Evidence document:

```text
docs/evidence/20260813_silver_mvp_execution_conforme.md
```

## Known Product Finding

Silver artifact generation/execution can duplicate rows on re-execution.

Observed duplicate before cleanup:

```text
producto_id=H3_PD_001
filas_silver=2
suma_silver=1360
filas_bronze=1
suma_bronze=680
diff_filas=1
diff_suma=680
```

Root issue:

```text
The generated Silver pipeline/notebook behaves as append-only or is not enforcing idempotent load semantics.
```

Required behavior:

```text
Generated Silver artifacts must implement idempotency using MERGE or deterministic deduplication by business_key + watermark.
```

MVP acceptance must require both:

```text
Dataproc execution state = SUCCEEDED
Post-execution validation = CONFORME
```

## Reentry Rule

When resuming this project:

1. Do not rediscover F2 tables, schema, filters, key, date column, metric, service, or connection.
2. Use F2 only as the validation control for Silver output.
3. Treat `bussinesrulessilver` as the SDD/frontend/evidence repository.
4. Do not assume the Silver backend source is inside `intercorp-fest-agent/main.py`.
5. Before changing backend code, locate the actual source repository/branch/image for Cloud Run service `silver-refinement-agent`.
6. The next real backend fix is idempotent Silver artifact generation.

## Commands To Locate Silver Backend Source

Run from Cloud Shell when backend source is needed:

```bash
PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
SERVICE="silver-refinement-agent"

gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="yaml(metadata.annotations,spec.template.spec.containers[0].image)"

gcloud builds list \
  --project="$PROJECT_ID" \
  --limit=20 \
  --format="table(id,createTime,source.repoSource.repoName,source.repoSource.branchName,images)"
```

## Do Not Repeat

Do not repeat these actions unless there is evidence of changed code or environment:

```text
- Search for alternative F2 tables.
- Redo F2 preflight discovery.
- Reinspect whether F2 date_column is required.
- Debate using bronze_fecha_ingesta as a business date.
- Use /reconciliation/drafts.
- Treat Dataproc SUCCEEDED alone as final business success.
- Assume intercorp-fest-agent/main.py is the Silver backend source without verifying Cloud Run image/build provenance.
```
