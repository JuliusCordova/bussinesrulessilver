# Gemini ADK Backend Candidate - Conforme

Date: 2026-08-16  
Status: **CONFORME EN TEST**

## Cloud Build

- Build ID: `e01595dc-813e-4252-82bf-10c2c4b577f7`
- Status: `SUCCESS`
- Duration: `2m46s`
- Image: `us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent:agents-8.2.0-e01595dc-813e-4252-82bf-10c2c4b577f7`

## Deployment target

- Service: `silver-refinement-agent-merge-test`
- URL: `https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app`
- Production backend traffic was not modified.

## Passed gates

1. focused Python tests;
2. module compilation;
3. container build;
4. Artifact Registry push;
5. Cloud Run test deployment;
6. health response with version `8.2.0`;
7. CORS preflight;
8. exact catalog of five agents;
9. real `table-profiler` Gemini ADK execution;
10. canonical BigQuery evidence with rows and columns.

## Contract correction

Agent responses separate:

- `output`: Gemini interpretation;
- `evidence`: canonical structured output from deterministic BigQuery tools.

All metrics shown by the frontend and checked by deployment gates use `evidence`, never narrative LLM formatting.

## Decision

Backend 8.2.0 is eligible for frontend candidate integration testing. It is not yet approved for production promotion.
