# Governed Dynamic Mapping Checkpoint

Date: 2026-08-17

## Status

Implemented in `main`; ready for candidate build and manual acceptance. Production traffic is unchanged.

## Corrections

- Removed the obsolete `cat_producto` mapping seed.
- Initial mapping is generated from the confirmed selected-table schema.
- The deterministic action calls the existing governed workflow recommendation engine.
- Added Gemini ADK `mapping-advisor`.
- Agent evidence is rebuilt canonically from the selected schema and fresh BigQuery profile.
- Mapping rows are editable:
  - include/exclude;
  - source column;
  - target column;
  - target data type;
  - transformation;
  - add/remove mapping.
- Agent recommendations expose confidence, reason, risk and approval requirement.
- The approved mapping, not `sourceColumns`, now feeds specification and artifact generation.

## Safety gates

- Duplicate or empty target names block confirmation.
- At least one included mapping is required.
- The candidate smoke profiles `pagos_primas`.
- The mapping advisor must return exactly the selected schema columns.
- Any `producto_id` seed leak fails the build.
- All recommendations require human confirmation.

## Verification

- TypeScript project build: conformant.
- Vite production build: conformant.
- Python modules compile: conformant.
- Full Python/ADK tests execute in Cloud Build candidate because the local scratch environment does not contain Google ADK.

## Candidate deployment

```bash
cd ~/bussinesrulessilver
git pull --ff-only origin main
bash scripts/deploy_dynamic_profile_candidates.sh
```
