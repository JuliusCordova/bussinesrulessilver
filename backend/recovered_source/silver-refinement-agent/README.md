# Recovered Silver Refinement Backend Source

This folder contains curated backend modules recovered from the deployed Cloud Run image.

## Source

Image:

`us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent:qg-f7a9117`

Digest:

`sha256:1ece1c196b3d52cb41dfb78e64f5ee1502eeee905167622e6cbdc85dd87566f3`

## Included Modules

- `modules/silver_workflow`
- `modules/silver_intelligent_mapping`

These modules were selected because they contain the real Silver Workflow API, mapping recommendation logic, load strategy models, and PySpark compilation behavior.

## Excluded Material

The complete Docker filesystem, generated files, cache files, and the incomplete Cloud Run source ZIP were intentionally excluded.

## Known Finding

`INCREMENTAL_WATERMARK` compiles to append behavior in `silver_intelligent_mapping/compiler.py`. For catalog/dimension tables such as `seguros_silver.cat_producto`, this can create duplicates on reruns unless MERGE or deterministic deduplication is enforced.
