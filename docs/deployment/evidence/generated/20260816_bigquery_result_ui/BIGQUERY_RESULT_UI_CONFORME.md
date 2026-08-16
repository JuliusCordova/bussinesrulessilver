# BigQuery Post-Execution Result UI - Evidence

Date: 2026-08-16  
Status: **CONFORME EN CÓDIGO / PENDIENTE DE DESPLIEGUE**

## Objective

Completar la acción `Ver resultado` para consultar y mostrar la validación BigQuery posterior a Dataproc.

## Implemented behavior

The frontend now:

1. calls `POST /executions/{execution_id}/result`;
2. shows a visible processing state while BigQuery validation runs;
3. stores the validation response in workflow state;
4. displays:
   - Silver row count;
   - distinct business-key count;
   - duplicate count;
   - Bronze/Silver difference count;
   - metric sum;
   - source and target tables;
   - business keys;
   - validation timestamp;
   - every validation check with PASS, FAIL or SKIPPED;
5. marks the workflow `SUCCEEDED` only when the response is conformant;
6. marks it `FAILED` and exposes technical evidence when BigQuery validation is not conformant.

The periodic Dataproc synchronization also consumes `validation_result` when the backend includes it.

## Files

- `src/App.tsx`
- `src/types.ts`
- `src/styles.css`

## Validation

GitHub Actions:

- Workflow: `Silver Agents Tests`
- Run: `31974546702`
- Commit: `4274f4fd974300c0b6fc62caf870035b73c93b94`
- Conclusion: `success`
- URL: https://github.com/JuliusCordova/bussinesrulessilver/actions/runs/31974546702

Validated jobs:

- Python compile and focused backend tests: PASS
- Frontend dependency installation: PASS
- TypeScript compilation: PASS
- Vite production build: PASS

## Deployment status

This change is committed and tested but has not yet been deployed to the Cloud Run frontend.

The production frontend remains:

`https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app`

Deployment will be performed after the next generalization increment or as a controlled candidate, according to the sprint plan.
