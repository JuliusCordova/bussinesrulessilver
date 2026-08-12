# Plan de Validacion - Business Rules Silver

## Objetivo

Validar que el frontend permita operar de punta a punta el flujo Bronze to Silver usando `silver-refinement-agent`.

## Caso semilla

Origen:

- Proyecto: `proyectopersonal-480420`
- Dataset: `seguros_bronce`
- Tabla: `cat_producto`

Destino:

- Proyecto: `proyectopersonal-480420`
- Dataset: `seguros_silver`
- Tabla: `cat_producto`

Controles esperados:

- Filas origen: `13`
- Filas destino: `13`
- Distinct `producto_id`: `13`
- SUM `prima_base`: `21390`
- Watermark: `bronze_fecha_ingesta`

## Validacion documental

1. Verificar que SDD exista en `docs/specs`.
2. Verificar que discovery OpenAPI exista en `docs/discovery/openapi`.
3. Verificar que discovery BigQuery exista en `docs/discovery/bigquery`.
4. Verificar que reglas semilla esten documentadas.

## Validacion funcional UI

### VF-01 Catalogo

- Abrir UI.
- Seleccionar proyecto.
- Listar dataset `seguros_bronce`.
- Listar tabla `cat_producto`.
- Mostrar columnas.

### VF-02 Workflow

- Crear workflow.
- Capturar `workflow_id`.
- Mostrar `status` y `active_step`.

### VF-03 Fuente y destino

- Confirmar source Bronze.
- Confirmar target Silver.
- Permitir tabla nueva si aplica.

### VF-04 Incrementalidad

- Seleccionar `INCREMENTAL`.
- Definir `producto_id` como business key.
- Definir `bronze_fecha_ingesta` como watermark.

### VF-05 Mapping

- Generar recomendaciones.
- Editar mapping.
- Agregar campo calculado `prima_base_anualizada`.

### VF-06 Reglas

- Generar reglas.
- Guardar draft.
- Confirmar reglas.

### VF-07 Quality review

- Ejecutar quality review.
- Revisar advertencias y recomendacion.

### VF-08 Specification y artefactos

- Guardar specification.
- Capturar `spec_id`.
- Generar DDL.
- Generar paquete.
- Visualizar artefactos.

### VF-09 Ejecucion

- Crear execution.
- Validar paquete.
- Confirmar ejecucion.
- Ejecutar Dataproc.
- Sincronizar estado.

## Validacion backend directa

Antes de atribuir errores a UI, validar endpoint backend correspondiente con `curl` y OpenAPI.

## Validacion posterior F2

Despues de ejecutar Silver, usar reconciliacion como control posterior.

Referencia validada previamente:

- Reconciliation ID: `REC_F2_CAT_PRODUCTO_BRONZE_SILVER_2FA40C51`
- Resultado esperado: `CONFORME`

## Criterio de cierre MVP

El MVP se considera validado cuando:

1. Se crea workflow.
2. Se confirma fuente/destino.
3. Se genera y aprueba mapping/reglas.
4. Se genera specification.
5. Se generan DDL y paquete.
6. Se crea execution.
7. Se valida paquete.
8. Se ejecuta submit Dataproc con confirmacion.
9. Se muestra estado final o error accionable.
