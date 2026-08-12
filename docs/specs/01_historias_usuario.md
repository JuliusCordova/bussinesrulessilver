# Historias de Usuario - Business Rules Silver

## Contexto

Business Rules Silver es una demo operacional para diseñar, aprobar, generar y ejecutar reglas Bronze to Silver usando el backend `silver-refinement-agent`.

Caso semilla validado:

- Origen: `proyectopersonal-480420.seguros_bronce.cat_producto`
- Destino: `proyectopersonal-480420.seguros_silver.cat_producto`
- Business key: `producto_id`
- Watermark: `bronze_fecha_ingesta`
- Metrica de control: `prima_base`

## HU-01 - Seleccionar fuente Bronze

Como analista de datos, quiero buscar proyecto, dataset y tabla Bronze para iniciar un workflow Silver desde metadata real de BigQuery.

Criterios:

- Debe listar datasets y tablas con endpoints de catalogo.
- Debe permitir seleccionar `seguros_bronce.cat_producto`.
- Debe mostrar esquema, tipos, perfil y muestra cuando esten disponibles.

## HU-02 - Definir destino Silver

Como analista de datos, quiero definir dataset y tabla destino Silver para crear o actualizar una tabla gobernada.

Criterios:

- Debe permitir seleccionar `seguros_silver.cat_producto`.
- Debe permitir crear tabla destino si no existe.
- Debe preparar la generacion de DDL para la tabla destino.

## HU-03 - Definir incrementalidad

Como data engineer, quiero definir business key, watermark y modo de carga para controlar ejecuciones full o incrementales.

Criterios:

- Debe permitir modo `FULL` o `INCREMENTAL`.
- Debe proponer `producto_id` como business key.
- Debe proponer `bronze_fecha_ingesta` como watermark.

## HU-04 - Revisar mapping recomendado

Como analista, quiero recibir recomendaciones de mapping Bronze to Silver para acelerar el diseno de transformacion.

Criterios:

- Debe consumir `/silver-workflows/{workflow_id}/mapping-recommendations`.
- Debe permitir editar mapping recomendado.
- Debe permitir crear campos derivados.

## HU-05 - Definir reglas de negocio

Como usuario de negocio/datos, quiero generar, editar y aprobar reglas de negocio para transformar y validar datos Silver.

Criterios:

- Debe generar reglas con backend/agente.
- Debe permitir editar y guardar draft.
- Debe confirmar/aprobar reglas antes de generar artefactos.

## HU-06 - Generar artefactos

Como data engineer, quiero generar specification, DDL, notebook y paquete tecnico para ejecutar la transformacion.

Criterios:

- Debe generar `spec_id`.
- Debe generar artefactos como `SILVER_DDL`, `NOTEBOOK`, `PYSPARK_SCRIPT` y `MANIFEST_JSON`.
- Debe permitir visualizar contenido de artefactos.

## HU-07 - Ejecutar Dataproc

Como operador demo, quiero ejecutar el paquete en Dataproc desde la UI con confirmacion explicita.

Criterios:

- Debe crear execution.
- Debe validar paquete.
- Debe ejecutar `/executions/{execution_id}/submit`.
- Debe sincronizar y mostrar estado.

## HU-08 - Consultar evidencia

Como responsable de demo, quiero consultar estado, artefactos y ejecucion para demostrar trazabilidad end-to-end.

Criterios:

- Debe mostrar `workflow_id`, `spec_id` y `execution_id`.
- Debe mostrar status del workflow y execution.
- Debe dejar visible la recomendacion de ejecutar reconciliacion posterior como control F2.
