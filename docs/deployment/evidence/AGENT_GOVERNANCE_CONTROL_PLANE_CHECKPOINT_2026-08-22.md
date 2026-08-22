# Agent Governance Control Plane — Checkpoint

Date: 2026-08-22
Repository: `JuliusCordova/bussinesrulessilver`
Branch: `feat/agent-governance-control-plane-preview`
Base: `main`

## Status

**CHECKPOINT SAVED — IMPLEMENTATION IN PROGRESS / NOT YET PROMOTED**

This checkpoint freezes the product and architecture decisions agreed before continuing the Agent Governance preview.

## Canonical UI source

The existing Business Rules Silver governance preview remains the canonical visual and interaction reference:

```text
preview/governance-dashboard/Dockerfile
preview/governance-dashboard/index.html
preview/governance-dashboard/app.js
preview/governance-dashboard/nginx.conf
preview/governance-dashboard/styles.css
```

The existing Business Rules governance dashboard is not modified by this work.

## Functional scope

The new control plane is **not** limited to Business Rules Silver agents.

Its functional estate is:

> **All Google ADK agents/deployments discoverable inside the configured Google Cloud projects and regions.**

Business Rules Silver contributes only the validated dashboard UI/UX pattern.

Required behavior:

- every discovered `google-adk` deployment appears in the technical inventory;
- agents without governance metadata remain visible as pending / not assessed;
- the dashboard primary view is logical-agent-centric;
- deployments / Reasoning Engines / versions are secondary drill-down detail;
- several deployments may map to one governed logical agent;
- discovery is not hard-coded to Business Rules, Ayniq, PrimaDemo or another product family;
- configured multi-project / multi-region discovery must consolidate the estate.

North Star:

> Todos los agentes Google ADK existentes dentro del alcance GCP configurado deben aparecer en el dashboard, estén gobernados o no.

## Current implementation branch

Independent work is isolated in:

```text
feat/agent-governance-control-plane-preview
```

Current preview artifacts:

```text
preview/agent-governance-dashboard/Dockerfile
preview/agent-governance-dashboard/index.html
preview/agent-governance-dashboard/app.js
preview/agent-governance-dashboard/nginx.conf
scripts/deploy_agent_governance_dashboard_preview.sh
docs/development/AGENT_GOVERNANCE_CONTROL_PLANE_PREVIEW.md
```

The Agent Governance preview reuses the canonical Business Rules stylesheet from `preview/governance-dashboard/styles.css` rather than inventing a new visual system.

## Backend contract currently targeted

The preview consumes the already validated Agent Governance API contracts:

```text
GET  /health
GET  /agent-governance/summary
GET  /agent-governance/agents
GET  /agent-governance/agents/{agent_id}
GET  /agent-governance/deployments
GET  /agent-governance/findings
POST /agent-governance/discovery/refresh
```

Current validated estate baseline from the previous discovery checkpoint:

```text
Reasoning Engines observed = 24
Google ADK deployments     = 23
```

That number is only the current observed baseline for `proyectopersonal-480420/us-central1`; it must not become a hard-coded product assumption.

## Guardrails

- no modification of Google ADK runtime agents;
- no prompt interception;
- no tool interception;
- no kill switch / runtime enforcement in this scope;
- no automatic logical-agent creation from names alone;
- no change to the existing `business-rules-silver-governance-preview` service;
- no change to `preview/governance-dashboard/`;
- no production promotion at this checkpoint.

## Next step after checkpoint

Continue the independent preview implementation, validate the all-ADK estate behavior, deploy to an isolated Cloud Run preview service, and perform visual validation against the canonical Business Rules governance dashboard pattern before any merge or promotion decision.
