# Candidate: Quality Review, artifact downloads and persistent agent governance

## Status

**READY FOR CANDIDATE DEPLOYMENT**

Production remains pinned to the previously validated cut:

- Backend revision: `silver-refinement-agent-validated-20260817012813`
- Backend digest: `sha256:e40cb0ba612a78040020619082ce316bb648755d5817178ceceee9915ae79bfc`
- Frontend revision: `business-rules-silver-ui-validated-20260817013232`

The changes described here have not been promoted to production.

## Scope completed

### Governed Quality Review

The former passive button is now a backend-backed gate:

1. saves the current Silver specification;
2. sends the approved deterministic or agent-recommended quality rules;
3. persists the Quality Review decision;
4. enables package generation only after an approved response.

### Artifact downloads

The artifact API exposes a governed binary download endpoint for every current artifact:

`GET /silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}/download`

The UI exposes downloads after generation for:

- Silver DDL;
- Dataproc notebook;
- PySpark script;
- manifest;
- specification;
- mapping;
- artifact package ZIP.

### Persistent agent governance

Unlike an in-memory dashboard, Silver agent runs are persisted in BigQuery table:

`proyectopersonal-480420.dataops_control.silver_agent_governance_runs`

Recorded evidence includes:

- run and session identifiers;
- agent and status;
- requester;
- source and target tables;
- event count and duration;
- start and finish timestamps;
- evidence JSON;
- error details.

AgentOps exposes:

- `GET /agentops/governance/summary`
- `GET /agentops/governance/runs`
- existing execution, alert, health and dashboard endpoints.

The seventh UI step combines these services into a governance dashboard with registry, KPIs, persistent run history, platform health, execution history and alerts.

## Verification completed in development environment

Frontend:

- TypeScript project build: **PASS**
- Vite production bundle: **PASS**
- 19 modules transformed
- bundle produced successfully

Candidate pipelines now assert:

- governance summary and run contracts;
- artifact download route in OpenAPI;
- Quality Review UI;
- artifact download UI;
- persistent governance dashboard labels;
- production/test backend binding rules.

## Candidate deployment

Run only in the test environment:

```bash
cd ~/bussinesrulessilver
git pull --ff-only origin main
bash scripts/deploy_dynamic_profile_candidates.sh
```

Manual acceptance:

1. execute Quality Review and verify package generation remains disabled until approval;
2. generate the package and download notebook, PySpark, DDL and ZIP;
3. run at least one ADK agent;
4. open step **7 Gobierno** and verify the run appears after refresh;
5. reload the browser and verify the run remains visible;
6. validate health, executions and alerts;
7. do not promote to production until explicit acceptance.
