# Requerimientos No Funcionales - Business Rules Silver

## RNF-01 Demo sin login

La primera version no tendra autenticacion por usuario y contrasena. El alcance es demo controlada.

## RNF-02 Separacion de producto

Business Rules Silver debe ser un frontend separado de Cuadratura. La reconciliacion F2 se conserva como control posterior, no como experiencia principal.

## RNF-03 Trazabilidad operacional

La UI debe mostrar identificadores clave durante todo el flujo:

- `workflow_id`
- `spec_id`
- `execution_id`
- `status`
- `active_step`
- `available_actions`

## RNF-04 Seguridad operativa de ejecucion

El boton `Ejecutar Dataproc` debe requerir confirmacion explicita antes de invocar submit.

## RNF-05 Usabilidad

La experiencia debe ser un wizard de 6 pasos con progreso visible y panel de estado lateral.

Pasos:

1. Origen y destino.
2. Incrementalidad y watermark.
3. Mapping.
4. Reglas de negocio.
5. Validacion y artefactos.
6. Ejecucion Dataproc.

## RNF-06 Observabilidad

La UI debe mostrar:

- errores HTTP
- errores de validacion backend
- mensajes de negocio
- estado de ejecucion
- resultado de validacion de paquete

## RNF-07 Resiliencia UX

La UI debe permitir retomar un workflow existente por `workflow_id` si el usuario recarga la pantalla.

## RNF-08 Versionamiento

Todo codigo, especificacion y documentacion debe versionarse en GitHub en:

- `JuliusCordova/bussinesrulessilver`

## RNF-09 Mantenibilidad

El frontend debe encapsular llamadas backend en un cliente API tipado o capa de servicios para evitar endpoints dispersos en componentes.

## RNF-10 Auditoria demo

Cada ejecucion demo debe poder explicar:

- fuente
- destino
- reglas aprobadas
- artefactos generados
- estado Dataproc
- control posterior sugerido
