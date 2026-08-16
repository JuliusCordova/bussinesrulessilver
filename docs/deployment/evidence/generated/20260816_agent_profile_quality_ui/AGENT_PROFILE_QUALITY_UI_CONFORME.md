# Gemini ADK Profiling and Quality Advisor UI - Evidence

Date: 2026-08-16  
Status: **CONFORME EN CÓDIGO / PENDIENTE DE DESPLIEGUE**

## Objective

Integrar en el wizard los agentes Gemini ADK de perfilamiento y recomendación de reglas, conservando aprobación humana obligatoria.

## Implemented flow

### Table profiling

The Incrementalidad step can call:

`POST /silver-agents/table-profiler/run`

The request contains the selected source and target tables, real schema, inferred load strategy, business keys, watermark and physical design.

The UI presents:

- BigQuery row count;
- profiled-column count;
- critical-column count;
- business-key candidates;
- ADK session identifier;
- explicit indication that metrics come from BigQuery.

### Quality recommendations

The Reglas step can call:

`POST /silver-agents/quality-rule-advisor/run`

The advisor evaluates factual evidence for:

- nulls in critical fields;
- declared or candidate-key uniqueness;
- low-cardinality domains;
- current PASSING, FAILING or NEEDS_VALUE_SAMPLE state;
- confidence;
- evidence.

### Human approval

Every proposal starts as pending.

The user must select each proposal explicitly. Only selected rules are transformed to the backend quality-rule contract and sent to:

- quality review;
- artifact/package generation;
- notebook specification.

No Gemini recommendation is automatically approved.

When no proposal is approved, the existing deterministic baseline remains an explicit fallback.

## Agent safety

- Agent responses must be valid JSON.
- Markdown JSON fences are normalized before parsing.
- Invalid/non-object output blocks the action and is shown as a backend error.
- RAG is not used.
- BigQuery evidence remains the factual source.
- Agent session ID is retained for traceability.

## Files

- `src/App.tsx`
- `src/types.ts`
- `src/styles.css`
- existing typed API contract in `src/api.ts`

## Validation

GitHub Actions:

- Workflow: `Silver Agents Tests`
- Run: `31975105805`
- Commit: `0e977fab2c3906326f9dfc2fa0594717a1105f31`
- Conclusion: `success`
- URL: https://github.com/JuliusCordova/bussinesrulessilver/actions/runs/31975105805

Validated:

- Python compile;
- focused backend tests;
- TypeScript compile;
- Vite production build.

## Deployment status

The integration is committed and tested. The production backend does not yet expose the Silver Agents endpoints because the 8.2.0 candidate has not been deployed. Frontend promotion must occur only after the backend candidate passes health, CORS, endpoint and real-table smoke tests.
