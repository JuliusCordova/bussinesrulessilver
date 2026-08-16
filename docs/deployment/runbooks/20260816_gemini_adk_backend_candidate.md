# Gemini ADK Backend Candidate Deployment Runbook

Date: 2026-08-16  
Target: `silver-refinement-agent-merge-test`  
Production traffic: **not modified**

## Purpose

Build and validate the Silver Refinement 8.2.0 candidate with Gemini ADK agents before any production promotion.

## Canonical command

Run from Cloud Shell:

```bash
cd ~/bussinesrulessilver
git pull --ff-only origin main

gcloud builds submit . \
  --project=proyectopersonal-480420 \
  --config=cloudbuild.backend-agents-candidate.yaml
```

## Automated gates

The pipeline stops on any failure and performs:

1. focused backend tests;
2. Python compilation;
3. candidate image build;
4. image push to Artifact Registry with immutable Cloud Build ID;
5. deployment to `silver-refinement-agent-merge-test`;
6. health assertion for version `8.2.0`;
7. CORS preflight assertion;
8. exact five-agent catalog assertion;
9. real Gemini ADK table-profiler call;
10. BigQuery profile assertion for `seguros_bronce.cat_producto`.

## Safety

- Production service `silver-refinement-agent` is not changed.
- Production frontend is not changed.
- The existing test service is the only deployment target.
- The candidate is not promoted automatically.
- Human approval remains mandatory for quality-rule proposals.

## Expected final evidence

A successful build prints a compact JSON object with:

- health/version;
- five agent names;
- profiled table;
- row count;
- ADK session ID.

Only after this output is conformant should the frontend candidate be built against the test backend.
