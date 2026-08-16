# Dynamic Profile Candidate - Ready to Deploy

Date: 2026-08-16

## Status

**READY FOR CANDIDATE DEPLOYMENT**

No production traffic was changed in this checkpoint.

## Candidate gates

The backend Cloud Build now fails unless all of the following are true:

- Python modules and focused tests compile and pass.
- The ADK profiler runs against `seguros_bronce.pagos_primas`.
- Canonical evidence identifies exactly `proyectopersonal-480420.seguros_bronce.pagos_primas`.
- The profiled schema does not leak `producto_id` from the seed case.
- The profile PDF endpoint returns HTTP 200, `application/pdf`, a `%PDF-` header and non-empty content.

The frontend Cloud Build now fails unless:

- TypeScript and Vite production build pass.
- The bundle targets the candidate backend.
- The bundle contains the hybrid target-table selector.
- The bundle contains editable load inference.
- The bundle contains explained validation.
- The bundle contains PDF report generation.

## One-block deployment

Run from Cloud Shell:

```bash
cd ~/bussinesrulessilver
bash scripts/deploy_dynamic_profile_candidates.sh
```

## Manual acceptance

Use the candidate frontend and validate:

1. Select `seguros_bronce.pagos_primas`.
2. Confirm that the detected schema belongs to `pagos_primas` and does not show `producto_id`.
3. Open the Silver table selector; choose an existing table, then test a new name.
4. Run profiling and review the exact profiled table.
5. With zero safe key candidates, confirm that automatic inference proposes `FULL`.
6. Select a key manually and confirm that the source changes to `USER`.
7. Generate the PDF, inspect it in the embedded viewer and download it.

Production promotion is allowed only after these seven checks pass.
