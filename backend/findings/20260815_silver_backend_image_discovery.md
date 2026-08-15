# Silver Backend Image Discovery - 2026-08-15

## Hallazgo principal

El source ZIP referenciado por Cloud Run metadata fue inspeccionado, pero no contenía la superficie funcional actual de Silver Workflow.

El código efectivo del backend desplegado fue encontrado dentro de la imagen:

`us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent:qg-f7a9117`

Digest observado:

`sha256:1ece1c196b3d52cb41dfb78e64f5ee1502eeee905167622e6cbdc85dd87566f3`

## Ubicación del código funcional

Código relevante extraído desde la imagen:

- `backend/source_discovery/silver-refinement-agent/image_fs/app/modules/silver_workflow/`
- `backend/source_discovery/silver-refinement-agent/image_fs/app/modules/silver_intelligent_mapping/`

## Módulos clave

- `silver_workflow/router.py`: endpoints `/silver-workflows`
- `silver_workflow/service.py`: estados y acciones del workflow
- `silver_workflow/mapping_recommendation.py`: estrategia de carga y mapping
- `silver_intelligent_mapping/compiler.py`: generación PySpark / estrategia de escritura

## Riesgo identificado

En `silver_intelligent_mapping/compiler.py`, la estrategia `INCREMENTAL_WATERMARK` compila a modo `append`.

Para una tabla catálogo como `seguros_silver.cat_producto`, esto puede generar duplicados si se reejecuta el pipeline sobre la misma ventana de datos.

Evidencia observada:

- Dataproc terminó en `SUCCEEDED`
- Silver quedó inicialmente con 14 filas y 13 productos distintos
- Producto duplicado: `H3_PD_001`
- Se corrigió manualmente con deduplicación por `producto_id`
- Resultado final: 13 filas, 13 productos distintos, `SUM(prima_base)=21390`

## Decisión técnica pendiente

Para tablas catálogo/dimensión con business key estable, el flujo Silver debe usar una de estas opciones:

1. `MERGE` por `business_key`
2. deduplicación determinística antes de escribir
3. validación post-ejecución que bloquee estado exitoso si existen duplicados

Para el MVP, Dataproc `SUCCEEDED` no debe ser el único criterio de éxito. Debe existir validación BigQuery posterior.
