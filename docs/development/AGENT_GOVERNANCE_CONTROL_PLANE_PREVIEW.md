# Agent Governance — Independent Control Plane Preview

Date: 2026-08-22
Repository: `JuliusCordova/bussinesrulessilver`
Branch: `feat/agent-governance-control-plane-preview`

## Objective

Build an independent Google ADK Agent Governance control plane using the already validated **Business Rules Silver Governance Dashboard** as the canonical UI/interaction pattern.

This work does **not** redesign that dashboard and does not modify its existing preview implementation.

## Canonical visual source

The source of truth is the existing code on `main`:

```text
preview/governance-dashboard/Dockerfile
preview/governance-dashboard/index.html
preview/governance-dashboard/app.js
preview/governance-dashboard/nginx.conf
preview/governance-dashboard/styles.css
```

Canonical blobs observed at the start of this work:

```text
Dockerfile  214ffb5315f57f348a39926ed8c454fba15c158f
index.html  43c02174581ebb43e7af6422ccc056baa84fd91a
app.js      8dce5bb5b52f22e99a0300aa98d2e39221f33652
nginx.conf  bfbdbe0093260a82f74f6994f487aea5e82b5d4e
styles.css  a4494be66ffcd39b58a945e11bf5c86d43ec2f5f
```

## Reuse decision

The new Agent Governance preview reuses the same visual system rather than recreating it.

Its Dockerfile copies the canonical stylesheet directly:

```dockerfile
COPY preview/governance-dashboard/styles.css /usr/share/nginx/html/styles.css
```

Therefore the new preview uses the exact dashboard CSS from Business Rules Silver.

The new HTML and JavaScript preserve the same interaction model:

- left navigation shell;
- executive KPI cards;
- dashboard panels;
- interactive rows/cards;
- side detail drawer;
- deep links;
- isolated Cloud Run preview;
- no changes to the productive Business Rules UI.

## Agent Governance domain adaptation

Only the domain and data contracts are changed.

Business Rules concepts such as runs, Silver artifacts and DataOps health are replaced by Agent Governance concepts supported by the validated APIs:

- governed logical agents;
- governance compliance status;
- business/technical ownership;
- risk;
- autonomy;
- deterministic assessment score;
- policy references;
- required controls;
- findings and finding history;
- observed Google ADK deployments.

The executive view deliberately keeps provider deployment terminology secondary. The primary question is:

> ¿Cuántos agentes tenemos, quién responde por ellos, qué riesgo tienen y cuáles están realmente gobernados?

## Independent preview files

```text
preview/agent-governance-dashboard/Dockerfile
preview/agent-governance-dashboard/index.html
preview/agent-governance-dashboard/app.js
preview/agent-governance-dashboard/nginx.conf
scripts/deploy_agent_governance_dashboard_preview.sh
```

The existing directory remains untouched:

```text
preview/governance-dashboard/
```

## Backend contract

The independent frontend proxies same-origin `/api/*` requests through nginx to the already validated Feature 56 preview API:

```text
https://atlas-datagob-api-f56-preview-mkqutd4koq-uc.a.run.app
```

Consumed contracts:

```text
GET  /health
GET  /agent-governance/summary
GET  /agent-governance/agents
GET  /agent-governance/agents/{agent_id}
GET  /agent-governance/deployments
GET  /agent-governance/findings
POST /agent-governance/discovery/refresh
```

The UI does not invoke, pause, kill, alter prompts, alter tools or otherwise mutate Google ADK runtime agents.

## Preview deployment

Target isolated service:

```text
agent-governance-adk-preview
```

Deployment script:

```bash
PROJECT_ID=proyectopersonal-480420 \
REGION=us-central1 \
bash scripts/deploy_agent_governance_dashboard_preview.sh
```

The script builds a temporary context that includes the **real canonical Business Rules governance stylesheet**, validates the Agent Governance API contracts, deploys only the new preview service and performs a same-origin proxy smoke test.

## Guardrail

`business-rules-silver-governance-preview` and `preview/governance-dashboard/` are not changed by this feature.
