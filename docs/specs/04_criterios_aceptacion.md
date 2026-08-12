# Criterios de Aceptacion - Business Rules Silver

## CA-01 Crear workflow desde fuente Bronze

Dado el proyecto `proyectopersonal-480420`, cuando el usuario seleccione `seguros_bronce.cat_producto`, entonces la UI debe crear un workflow Silver y mostrar `workflow_id`.

## CA-02 Confirmar destino Silver

Dado un workflow creado, cuando el usuario defina `seguros_silver.cat_producto`, entonces la UI debe confirmar fuente/destino y avanzar el wizard.

## CA-03 Configurar incrementalidad

Dado el esquema de `cat_producto`, cuando el usuario configure incrementalidad, entonces la UI debe aceptar:

- business key: `producto_id`
- watermark: `bronze_fecha_ingesta`
- modo: `INCREMENTAL`

## CA-04 Generar mapping recomendado

Dado un workflow con fuente confirmada, cuando el usuario solicite recomendaciones, entonces la UI debe mostrar mapping editable y versionado.

## CA-05 Crear campo derivado

Dado el mapping editable, cuando el usuario agregue `prima_base_anualizada`, entonces la UI debe permitir la expresion:

```sql
CASE WHEN periodicidad = 'MENSUAL' THEN prima_base * 12 ELSE prima_base END
```

## CA-06 Generar reglas de negocio

Dado un workflow con mapping revisado, cuando el usuario genere reglas, entonces la UI debe mostrar reglas editables y permitir guardar draft.

## CA-07 Confirmar reglas

Dado un draft de reglas, cuando el usuario confirme/apruebe, entonces la UI debe invocar confirmacion backend y bloquear cambios accidentales antes de generar artefactos.

## CA-08 Ejecutar quality review

Dado reglas confirmadas, cuando el usuario ejecute quality review, entonces la UI debe mostrar resultado, advertencias y recomendacion.

## CA-09 Generar specification

Dado quality review completado, cuando el usuario guarde specification, entonces la UI debe capturar y mostrar `spec_id`.

## CA-10 Generar DDL y artefactos

Dado un `spec_id`, cuando el usuario genere artefactos, entonces la UI debe mostrar al menos:

- DDL
- Notebook o PySpark script
- Manifest
- Specification JSON

## CA-11 Validar paquete

Dado un `execution_id`, cuando el usuario valide paquete, entonces la UI debe mostrar estado `VALIDATED` o error accionable.

## CA-12 Ejecutar Dataproc

Dado un paquete validado, cuando el usuario confirme ejecucion Dataproc, entonces la UI debe invocar `/executions/{execution_id}/submit` y mostrar estado de submission.

## CA-13 Sincronizar estado

Dado una ejecucion enviada, cuando el usuario sincronice estado, entonces la UI debe mostrar estado actualizado de ejecucion.

## CA-14 Evidencia final

Al terminar el flujo, la UI debe mostrar:

- workflow_id
- spec_id
- execution_id
- status final
- artefactos generados
- recomendacion de control F2 posterior
