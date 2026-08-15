# Silver Frontend Production - Evidence

## Executive Summary

The Business Rules Silver frontend was deployed to Cloud Run production and validated against the production Silver backend.

Final result: **CONFORME**

This freezes the deterministic MVP production state.

## Frontend Production Service

- Service: `business-rules-silver-ui`
- URL: `https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app`
- Revision: `business-rules-silver-ui-00002-zhr`
- Traffic: `100%`
- Image tag: `us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui:prod-8ea983d-nginx8080`
- Image digest: `sha256:9822d95c5f0c74f7e08f06fa815f63aaf1698072db27fe047df3d70ca6324e0c`
- HTTP check: `HTTP/2 200`

## Backend Production Dependency

- Backend service: `silver-refinement-agent`
- Backend URL: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`
- Backend revision: `silver-refinement-agent-mergefix-1786834335`
- Backend digest: `sha256:7b511767b45127090e85c60b584dfa8fb0824907727f4e245be73b21bb021ec8`
- Backend traffic: `100%`

## End-to-End Production Execution From Frontend

The full wizard flow completed from the production frontend.

- Workflow ID: `workflow_85a570fcbf0e45e39111fa7f9ff16258`
- Spec ID: `spec_83f0eee67a304f13a5f545114b46d348`
- Execution ID: `exec_29fbf7ca1efa47728dfb9708eec0a88d`
- Dataproc batch: `silver-exec-29fbf7ca1efa47728dfb9708eec0a88d`
- Dataproc state: `SUCCEEDED`
- Frontend state: `SUCCEEDED`
- Dataproc sync time shown in UI: `23:18:42`

## Scope Validated

- Source table: `proyectopersonal-480420.seguros_bronce.cat_producto`
- Target table: `proyectopersonal-480420.seguros_silver.cat_producto`
- Business key: `producto_id`
- Watermark column: `bronze_fecha_ingesta`
- Load strategy: `MERGE`
- Execution engine: Dataproc Serverless
- Frontend: Cloud Run production `business-rules-silver-ui`
- Backend: Cloud Run production `silver-refinement-agent`

## Acceptance Criteria

| Criterion | Result |
| --- | --- |
| Frontend Cloud Run service starts on port 8080 | PASS |
| Frontend URL returns HTTP 200 | PASS |
| Frontend uses production backend URL | PASS |
| Wizard creates workflow through production backend | PASS |
| Wizard generates package and execution | PASS |
| Dataproc execution completes | PASS |
| Final UI state is `SUCCEEDED` | PASS |

## Frozen MVP State

This is the production freeze point for the deterministic MVP.

Out of scope for this freeze:

1. Agentic code generation.
2. Agentic quality rule recommendation.
3. RAG over enterprise standards or historical notebooks.
4. Multi-table generalized production onboarding.

Those items remain planned for later sprints.
