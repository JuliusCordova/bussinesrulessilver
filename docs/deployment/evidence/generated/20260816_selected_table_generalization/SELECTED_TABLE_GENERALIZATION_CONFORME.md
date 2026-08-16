# Selected Table Generalization - Evidence

Date: 2026-08-16  
Status: **CONFORME EN CÓDIGO / PENDIENTE DE DESPLIEGUE**

## Objective

Generalizar el wizard Bronze-to-Silver para que el contrato técnico no dependa de `seguros_bronce.cat_producto`.

## Implemented behavior

When a source table is selected, the frontend now preserves its actual schema and deterministically infers:

- business-key candidate;
- watermark candidate;
- reconciliation metric candidate;
- load strategy;
- partitioning and clustering proposal;
- baseline quality rules.

## Strategy rules

- A stable non-trace `*_id` column is preferred as business key.
- A required key-like column is the fallback business-key candidate.
- TIMESTAMP, DATETIME or DATE columns with ingestion/update semantics are watermark candidates.
- A non-trace numeric column is a metric candidate.
- When business keys exist, the proposed strategy is `MERGE`.
- When no safe business key is detected, the proposed strategy is `FULL`; the UI does not simulate an unsafe MERGE.

## Quality baseline

For every inferred business key:

- NOT_NULL;
- UNIQUE.

For an inferred watermark:

- NOT_NULL.

If neither is available, the first REQUIRED column receives a NOT_NULL baseline rule.

These are deterministic MVP rules. Agentic recommendations remain subject to human approval in the following increment.

## Removed seed dependencies

The workflow no longer sends:

- fixed 13-row profile;
- fixed `producto_id`;
- fixed `bronze_fecha_ingesta`;
- fixed `prima_base`;
- fixed `cat_producto` generation reason;
- fixed `cat_producto_silver` placeholder;
- fixed schema-preview classifications.

The seed remains only as an explicit fallback when the real catalog/schema cannot be loaded.

## Files

- `src/App.tsx`
- `src/types.ts`

## Validation

GitHub Actions:

- Workflow: `Silver Agents Tests`
- Run: `31974865693`
- Commit: `8b95e815ec78088714cbea46c4da522ff2340705`
- Conclusion: `success`
- URL: https://github.com/JuliusCordova/bussinesrulessilver/actions/runs/31974865693

Validated:

- backend focused tests;
- Python compile;
- TypeScript compile;
- Vite production build.

## Known MVP limitation

Inference is intentionally conservative and deterministic. Composite keys, domain semantics, negative-value metrics and semantic rule recommendations require the profiling and quality-advisor agents, which are the next integration block.
