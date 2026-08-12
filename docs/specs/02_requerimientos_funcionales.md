# Requerimientos Funcionales - Business Rules Silver

## RF-01 Catalogo de metadata

La UI debe consultar metadata de BigQuery a traves del backend Silver.

Endpoints:

- `GET /silver-workflows/catalog/projects/{project_id}/datasets`
- `GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables`
- `GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}`

Debe mostrar:

- datasets
- tablas
- columnas
- tipos de datos
- candidatos a business key, watermark y metricas

## RF-02 Creacion de workflow

La UI debe crear un workflow Silver mediante:

- `POST /silver-workflows`

Debe almacenar en estado UI:

- `workflow_id`
- `status`
- `active_step`
- `available_actions`

## RF-03 Confirmacion de fuente y destino

La UI debe confirmar fuente Bronze y destino Silver mediante:

- `POST /silver-workflows/{workflow_id}/confirm-source`

Debe soportar:

- tabla destino existente
- tabla destino nueva
- opcion `create_if_not_exists`

## RF-04 Estrategia incremental

La UI debe permitir configurar:

- modo `FULL` o `INCREMENTAL`
- business key
- watermark column
- deduplicacion opcional
- politica de registros tardios como configuracion futura

Caso semilla:

- business key: `producto_id`
- watermark: `bronze_fecha_ingesta`

## RF-05 Mapping recomendado

La UI debe solicitar mapping recomendado mediante:

- `POST /silver-workflows/{workflow_id}/mapping-recommendations`

Debe permitir editar:

- columna origen
- columna destino
- tipo destino
- tipo de transformacion
- expresion
- descripcion

Tipos soportados en UI:

- `DIRECT_COPY`
- `RENAME`
- `CAST`
- `CALCULATED_FIELD`
- `CASE_WHEN`
- `COALESCE`
- `CONCAT`
- `ARITHMETIC_OPERATION`

## RF-06 Reglas de negocio

La UI debe permitir:

- generar reglas: `POST /silver-workflows/{workflow_id}/business-rules/generate`
- guardar draft: `PUT /silver-workflows/{workflow_id}/business-rules/draft`
- confirmar reglas: `POST /silver-workflows/{workflow_id}/business-rules/confirm`

Reglas semilla:

- `producto_id` obligatorio.
- `moneda` en `PEN`, `USD`.
- `periodicidad` en `MENSUAL`, `ANUAL`.
- `bronze_estado_registro = RECIBIDO`.
- conservar trazabilidad `bronze_*`.
- `prima_base_anualizada` como campo derivado opcional.

## RF-07 Quality review

La UI debe ejecutar revision de calidad mediante:

- `POST /silver-workflows/{workflow_id}/quality-review`

Debe mostrar:

- reglas evaluadas
- advertencias
- bloqueos
- recomendacion de avance

## RF-08 Specification

La UI debe guardar specification mediante:

- `POST /silver-workflows/{workflow_id}/specification`

Debe capturar el `spec_id` devuelto por backend.

## RF-09 Artefactos

La UI debe generar artefactos mediante:

- `POST /silver-refinement/specs/{spec_id}/artifacts/ddl`
- `POST /silver-refinement/specs/{spec_id}/artifacts/generate`

Debe consultar:

- `GET /silver-refinement/specs/{spec_id}/artifacts`
- `GET /silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}`
- `GET /silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}/content`

Tipos esperados:

- `SILVER_DDL`
- `SPECIFICATION_JSON`
- `MAPPING_JSON`
- `TRANSFORMATIONS_JSON`
- `README`
- `MANIFEST_JSON`
- `PYSPARK_SCRIPT`
- `NOTEBOOK`
- `ARTIFACT_PACKAGE`

## RF-10 Ejecucion Dataproc

La UI debe permitir ejecucion real con confirmacion previa.

Endpoints:

- `POST /executions`
- `GET /executions/{execution_id}`
- `POST /executions/{execution_id}/validate-package`
- `POST /executions/{execution_id}/submit`
- `POST /executions/{execution_id}/sync-status`

Debe mostrar estados:

- `PENDING`
- `VALIDATED`
- `QUEUED`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`
