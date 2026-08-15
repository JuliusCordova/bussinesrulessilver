# Sprint Plan - Business Rules Silver

## Objetivo general

Construir un frontend y flujo backend para crear pipelines Bronze to Silver gobernados, con reglas de negocio, reglas de calidad, generación de artefactos, ejecución Dataproc y validación posterior.

## Sprint 0 - Canon y control

Estado: cerrado.

Entregables:

- Canon F2 documentado.
- Backend Silver identificado.
- OpenAPI descubierto.
- Imagen real identificada.
- Código backend curado en `backend/recovered_source`.
- Hallazgo `INCREMENTAL_WATERMARK -> append` documentado.
- `.gitignore` agregado para evitar ruido local.

## Sprint 1 - MVP determinístico estable

Objetivo:

Lograr que el flujo `seguros_bronce.cat_producto` -> `seguros_silver.cat_producto` funcione sin duplicados y con validación post-ejecución.

Alcance:

- Wizard frontend operativo.
- Backend real `silver-refinement-agent`.
- Selección real de datasets/tablas BigQuery.
- Creación de workflow.
- Mapping.
- Reglas.
- Artefactos.
- Dataproc.
- Validación final BigQuery.

Criterios de aceptación:

- Dataproc termina en `SUCCEEDED`.
- `row_count = 13`.
- `COUNT(DISTINCT producto_id) = 13`.
- `SUM(prima_base) = 21390`.
- Consulta de duplicados por `producto_id` no retorna filas.

## Sprint 2 - Corrección backend package generator

Objetivo:

Corregir el generador de package/notebook para soportar carga idempotente.

Problema actual:

- `INCREMENTAL_WATERMARK` compila a `append`.
- `MERGE` existe en el contrato, pero el backend rechaza package porque no tiene ejecutor MERGE/CDC.

Decisión técnica:

Implementar soporte de carga idempotente para tablas catálogo/dimensión usando `business_keys`.

Opciones:

1. MERGE real contra BigQuery.
2. Overwrite determinístico con deduplicación por business key.
3. Validación post-write obligatoria.

## Sprint 3 - Agentic Code Generator

Objetivo:

Crear un agente que genere `silver_pipeline.py`, notebook y artefactos desde un spec aprobado.

No requiere RAG en MVP.

Input:

- source table
- target table
- schema
- mapping
- business keys
- watermark
- load strategy
- quality rules
- physical design

Output:

- PySpark script
- notebook
- manifest
- README técnico
- evidencia de validación

## Sprint 4 - Quality Rules Advisor Agent

Objetivo:

Crear un agente que proponga reglas de calidad a partir del perfilamiento BigQuery.

Input:

- schema
- null counts
- distinct counts
- min/max
- top values
- contexto de negocio
- business key
- watermark

Output:

- reglas sugeridas
- severidad
- justificación
- evidencia del perfilamiento

Reglas semilla para `cat_producto`:

- `producto_id` NOT NULL
- `producto_id` UNIQUE
- `moneda IN ('PEN','USD')`
- `periodicidad IN ('MENSUAL','ANUAL')`
- `prima_base >= 0`
- `bronze_fecha_ingesta` NOT NULL
- `bronze_hash_origen` NOT NULL
- `bronze_estado_registro = 'RECIBIDO'`

## Sprint 5 - RAG opcional

RAG no entra al MVP.

Solo se evaluará si se requiere consultar:

- estándares corporativos;
- patrones históricos;
- políticas de gobierno;
- convenciones internas;
- notebooks aprobados.
