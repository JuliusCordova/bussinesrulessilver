# Governance Dashboard Preview V1 — Canonical Checkpoint

Date: 2026-08-19
Repository: `JuliusCordova/bussinesrulessilver`
Branch developed: `feat/governance-dashboard-preview`
Pull request: `#1 feat: isolated governance dashboard preview`
Target branch: `main`

## Status

**PREVIEW V1 INTERACTIVO: CONFORME**

This checkpoint records the independent interactive governance dashboard built for Business Rules Silver and its successful deployment/validation in Google Cloud Run.

The preview was intentionally developed outside the productive wizard. It consumes the canonical productive Silver Refinement / AgentOps APIs and does not introduce a second governance backend.

## Product scope

Dashboard title:

`Gobierno DataOps — Business Rules Silver`

Purpose:

- executive observability of Bronze → Silver refinement;
- persistent agent governance;
- AgentOps operational traceability;
- health and alerts;
- drill-down from executive metrics to operational detail.

## Preview deployment

Google Cloud project: `proyectopersonal-480420`

Region: `us-central1`

Independent Cloud Run service: `business-rules-silver-governance-preview`

Validated revision: `business-rules-silver-governance-preview-00002-szx`

Traffic: `100%`

Direct dashboard URL:

`https://business-rules-silver-governance-preview-913797829604.us-central1.run.app/`

Canonical backend:

`https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`

## Canonical APIs consumed

- `GET /health`
- `GET /agentops/dashboard`
- `GET /agentops/health`
- `GET /agentops/governance/summary`
- `GET /agentops/governance/runs`
- `GET /agentops/executions`
- `GET /agentops/alerts`
- `GET /silver-agents`

## V1 visual capabilities

Executive KPIs:

- agent runs;
- active agents;
- execution success rate;
- p90 duration calculated from persisted runs;
- generated artifacts;
- unread alerts.

Visual sections:

- execution trend;
- top agents;
- run status distribution;
- persistent agent history;
- platform health;
- AgentOps alerts;
- ADK agent registry;
- recent Silver executions;
- Business Rules Silver architecture flow.

## Interactive capabilities

The preview includes:

- clickable KPIs;
- date filtering from trend points;
- agent filtering from Top Agents;
- status filtering from execution distribution;
- visible/removable filters;
- Run Detail drawer;
- Agent Detail drawer;
- Execution Detail drawer;
- Alert Detail drawer;
- Health Detail drawer;
- side navigation to dashboard sections;
- deep links using URL hash.

Examples:

- `/#run/<run_id>`
- `/#agent/<agent_name>`

## Run Detail contract used

The current persistent governance contract exposes enough information for the V1 drill-down:

- `run_id`;
- `agent_name`;
- `session_id`;
- `status`;
- `requested_by`;
- `source_table`;
- `target_table`;
- `event_count`;
- `duration_ms`;
- `started_at`;
- `finished_at`;
- `error_message`.

The V1 detail uses these fields for operational traceability and timeline presentation without inventing backend information.

## Deployment automation

Deployment script:

`scripts/deploy_governance_dashboard_preview.sh`

The script validates:

1. local preview structure and JavaScript syntax when Node is available;
2. presence of interactive drill-down functions;
3. canonical backend and AgentOps contracts;
4. deployment of the isolated Cloud Run service;
5. deployed HTML/JS smoke tests;
6. direct dashboard and deep-link format output.

A false-negative smoke failure caused by `curl | grep -q` under `set -o pipefail` was corrected by downloading responses before applying assertions.

Fix commit:

`88814d3` — `fix: avoid curl broken-pipe false failures in preview smoke test`

## Independent validation evidence

Cloud Shell validation executed after deployment:

```text
=== PREVIEW INTERACTIVO: CONFORME ===
DIRECT_DASHBOARD_URL=https://business-rules-silver-governance-preview-913797829604.us-central1.run.app/
```

The validation confirmed that the deployed preview contains:

- dashboard title;
- interactive preview shell;
- AgentOps governance contract binding;
- `openRunDetail` drill-down;
- `openAgentDetail` drill-down.

## Governance decision

This checkpoint is approved to merge to `main` as the canonical source for the Governance Dashboard V1 code and evidence.

**Merge does not mean production promotion.**

The preview Cloud Run service remains the validated deployment target until a separate production promotion is explicitly executed and independently validated.

## Next phase — controlled production promotion

After merge, production promotion will be handled as a separate checkpoint with at least:

1. confirm exact `main` commit SHA;
2. validate current production baseline;
3. define whether the dashboard replaces/enhances Step 7 or gets a canonical direct production route;
4. build/deploy the exact approved source;
5. pin and verify Cloud Run revision/digest;
6. smoke-test direct dashboard URL and interactive drill-downs;
7. validate AgentOps/BigQuery persistence from production;
8. record evidence and declare the new production baseline only after PASS.

## Files introduced by the preview

- `preview/governance-dashboard/Dockerfile`
- `preview/governance-dashboard/nginx.conf`
- `preview/governance-dashboard/index.html`
- `preview/governance-dashboard/styles.css`
- `preview/governance-dashboard/app.js`
- `scripts/deploy_governance_dashboard_preview.sh`

## Canonical conclusion

At this checkpoint, Business Rules Silver has a validated independent Governance DataOps dashboard with executive observability and interactive operational drill-downs, deployed in an isolated Cloud Run preview and ready to be merged to `main`. Production promotion remains a subsequent controlled activity.
