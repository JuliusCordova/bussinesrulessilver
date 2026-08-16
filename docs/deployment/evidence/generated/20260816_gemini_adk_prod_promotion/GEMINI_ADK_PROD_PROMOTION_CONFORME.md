# Gemini ADK Production Promotion - Evidence

## Status

**PRODUCTION CONFORME**

Date: 2026-08-16

## Backend production

- Service: `silver-refinement-agent`
- URL: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`
- Revision: `silver-refinement-agent-agents820-20260816225819`
- Traffic: `100%`
- Version: `8.2.0`
- Image digest: `sha256:094c51ed5f7a34940a2bd82a5e78a4eb8b5a8084d822cab8c27d040ff0d898ae`
- Health: conformant
- CORS: conformant
- Five Gemini ADK agents: conformant

The promoted backend is the candidate previously validated end to end with Dataproc and mandatory post-execution BigQuery validation.

## Frontend production

- Service: `business-rules-silver-ui`
- URL: `https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app`
- Revision: `business-rules-silver-ui-00003-chr`
- Traffic: `100%`
- Image: `us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui:agents-prod-f859e34-20260816225819`
- HTTP result: `200`

## Bundle binding

The production frontend was rebuilt with:

`VITE_SILVER_API_URL=https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`

Verification results:

- production backend URL is present in the JavaScript bundle;
- test backend `silver-refinement-agent-merge-test` is absent;
- final result: `FRONTEND PROD CONFORME`.

## Promotion incident

The automated runbook promoted and verified the backend, then stopped before changing the frontend because the frontend service export did not contain `spec.template.metadata.name`.

The frontend was subsequently deployed using the already-built production image. No unvalidated image was introduced.

The runbook was corrected to support both Cloud Run export variants:

- services with an existing pinned template revision name;
- services without a template revision name.

## Production capabilities

Production now includes:

- selected-table BigQuery profiling with Gemini ADK;
- quality-rule recommendations based on nulls, cardinality and critical fields;
- explicit human approval of agent recommendations;
- deterministic artifact and PySpark generation;
- idempotent MERGE execution;
- Dataproc Serverless execution;
- mandatory post-execution BigQuery validation;
- final `SUCCEEDED` only when Dataproc and BigQuery validation are conformant;
- functional **Ver resultado** UI.

## Conclusion

Backend and frontend production promotion completed successfully.

Final status: **CONFORME**.
