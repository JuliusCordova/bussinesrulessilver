# Gemini ADK Frontend Candidate - Evidence

## Status

**CANDIDATE ACCESSIBLE / INTEGRATION READY**

Date: 2026-08-16

Production was not modified by this validation.

## Candidate

- Cloud Run service: `business-rules-silver-ui-agents-test`
- URL: `https://business-rules-silver-ui-agents-test-mkqutd4koq-uc.a.run.app`
- Revision: `business-rules-silver-ui-agents-test-00001-g9d`
- Backend candidate: `silver-refinement-agent-merge-test`
- Backend version validated previously: `8.2.0`

## Build and deployment

The frontend candidate image was built and deployed by Cloud Build execution:

`fbf3c586-c278-4a90-a5c0-3c0f8bb82110`

The build, image push and Cloud Run revision creation completed successfully. The original smoke step failed with HTTP 403 because the new frontend service did not yet have a public invoker binding.

The IAM binding was then added explicitly:

- member: `allUsers`
- role: `roles/run.invoker`

This was an access configuration issue, not an application build failure.

## Verification after IAM correction

### HTTP

The public candidate URL returned:

`HTTP/2 200`

### Browser verification

The candidate rendered the Business Rules Silver wizard successfully.

Observed live integration evidence:

- page title: `Business Rules Silver`;
- real Bronze and Silver dataset catalogs loaded;
- real source and target table catalogs loaded;
- selected table schema loaded, including `producto_id`, `prima_base` and `bronze_fecha_ingesta`;
- no frontend access error was displayed.

Loading these catalogs and schema requires successful communication from the frontend candidate to the backend candidate. Therefore the frontend-to-backend binding is operational.

## Agent scope included in the candidate

The candidate source includes:

- selected-table profiling with Gemini ADK;
- quality-rule recommendations with Gemini ADK;
- canonical structured evidence separated from LLM narrative output;
- explicit human approval before recommended rules enter the artifact package;
- deterministic fallback when no agent recommendations are approved;
- post-execution BigQuery result visualization.

## Remaining controlled functional validation

Before production promotion, execute one end-to-end test in the candidate UI:

1. create a test workflow;
2. run **Perfilar tabla con agente**;
3. verify canonical profile evidence;
4. run **Recomendar con Gemini ADK**;
5. approve selected recommendations manually;
6. generate and validate the package;
7. stop before Dataproc unless the execution test is explicitly authorized.

## Conclusion

The frontend candidate is publicly accessible and its live backend/catalog integration is operational. It is ready for the controlled functional agent workflow test. Production frontend and production backend remain unchanged by this candidate validation.
