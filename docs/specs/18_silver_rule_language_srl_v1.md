# SPEC 18 — Silver Rule Language (SRL) v1.0

Status: DRAFT
Branch: hotfix/frontend-product-ux-v1.1
Product: Business Rules Silver

## 1. Objetivo

Definir un lenguaje declarativo, determinístico, gobernado y versionable para expresar transformaciones Bronze→Silver, reglas de calidad y reglas de negocio. La IA podrá interpretar lenguaje natural y proponer SRL, pero SRL será validado y compilado por código determinístico antes de cualquier persistencia o ejecución.

## 2. Principios

1. AI interpreta intención; código gobierna contrato y ejecución.
2. Ninguna salida libre del LLM se ejecuta directamente.
3. SRL es legible por personas y máquinas.
4. Toda regla ejecutable debe tener versión, estado, hash y trazabilidad.
5. Solo reglas APPROVED pueden incluirse en un package ejecutable.
6. El artefacto ejecutado debe corresponder exactamente a una versión SRL aprobada.
7. El orquestador Silver existente queda fuera de alcance; SRL se integra mediante agentes/tools individuales y runtime existente.

## 3. Modos de creación

La UI debe ofrecer tres modos equivalentes:

- Constructor visual: controles determinísticos por tipo de regla.
- Pseudocódigo SRL: edición directa para usuarios avanzados.
- Lenguaje natural con IA: Gemini interpreta y propone SRL; el usuario confirma, corrige o rechaza.

Los tres modos convergen en el mismo parser, AST, validator y ciclo de aprobación.

## 4. Familias SRL v1.0

### 4.1 TRANSFORM

Transformaciones y campos derivados.

Ejemplos:

```text
COPY cliente_id TO cliente_id
CAST monto AS NUMERIC
DERIVE monto_comision = monto_reclamado * 0.10
DERIVE total = subtotal + impuesto
CONCAT nombre_completo = nombres, " ", apellidos
```

Operadores iniciales:

- COPY
- CAST
- DERIVE con ADD, SUBTRACT, MULTIPLY, DIVIDE
- CONCAT

### 4.2 CHECK

Reglas de calidad.

Ejemplos:

```text
CHECK ramo_id NOT_NULL
ON_FAIL BLOCK_LOAD
```

```text
CHECK moneda IN ["PEN", "USD"]
ON_FAIL WARN
```

```text
CHECK edad BETWEEN 18 AND 100
ON_FAIL QUARANTINE
```

```text
CHECK correo MATCHES "^[^@]+@[^@]+$"
ON_FAIL WARN
```

Operadores iniciales:

- NOT_NULL
- UNIQUE
- IN
- BETWEEN
- MATCHES

Runtime actions:

- OBSERVE_ONLY
- WARN
- QUARANTINE
- BLOCK_LOAD

Las restricciones existentes del runtime permanecen vigentes; por ejemplo, reglas table-level no deben aceptar QUARANTINE cuando el runtime no puede aislar filas.

### 4.3 WHEN / THEN

Reglas de negocio condicionales. Se define en v1.0 como contrato del lenguaje, pero su compilación/runtime se implementará después de estabilizar TRANSFORM y CHECK.

Ejemplos:

```text
WHEN estado_siniestro = "CERRADO"
THEN REQUIRE monto_pagado NOT_NULL
ON_FAIL BLOCK_LOAD
```

```text
WHEN tipo_cliente = "EMPRESA"
THEN REQUIRE ruc NOT_NULL
ON_FAIL BLOCK_LOAD
```

## 5. Arquitectura de interpretación

```text
Usuario
  |
  +--> Constructor visual --------+
  |                               |
  +--> SRL directo ---------------+--> Parser --> AST --> Validator --> Governed Contract
  |                               |
  +--> Lenguaje natural --> Gemini+
                               |
                               +--> propuesta SRL, nunca código ejecutable
```

Flujo de lenguaje natural:

1. El usuario escribe una regla.
2. El agente consulta el catálogo SRL y ejemplos aprobados.
3. Gemini propone una expresión SRL acotada.
4. El parser convierte SRL a AST.
5. El validator verifica schema, tipos, operadores y parámetros.
6. La UI muestra `Entendí tu regla así...`.
7. El usuario confirma, corrige o rechaza.
8. Solo tras confirmación se persiste como PENDING_APPROVAL/APPROVED según el workflow gobernado.
9. El compiler genera el contrato/runtime existente.

## 6. Regla crítica de IA

Gemini no debe construir directamente modelos Pydantic de runtime, SQL, Python o PySpark.

La salida del agente debe limitarse a un contrato simple:

```json
{
  "srl_version": "1.0",
  "family": "CHECK",
  "srl": "CHECK moneda IN [\"PEN\", \"USD\"]\nON_FAIL WARN",
  "interpretation": "La columna moneda solo admite PEN o USD.",
  "confidence": 0.94
}
```

El backend será responsable de convertir SRL a AST y de AST a contratos internos.

Se permite un único retry automático de reparación cuando la salida no parsea o no valida. Si vuelve a fallar, la UI no mostrará un traceback técnico como interacción principal; mostrará que la regla no pudo interpretarse con suficiente confianza y ofrecerá Builder o edición SRL.

## 7. AST canónico

### 7.1 CHECK

```json
{
  "srl_version": "1.0",
  "family": "CHECK",
  "column": "moneda",
  "operator": "IN",
  "arguments": ["PEN", "USD"],
  "runtime_action": "WARN"
}
```

### 7.2 TRANSFORM

```json
{
  "srl_version": "1.0",
  "family": "TRANSFORM",
  "target_column": "monto_comision",
  "operation": "MULTIPLY",
  "operands": [
    {"column": "monto_reclamado"},
    {"scalar": 0.10}
  ]
}
```

### 7.3 BUSINESS

```json
{
  "srl_version": "1.0",
  "family": "BUSINESS",
  "when": {
    "column": "estado_siniestro",
    "operator": "EQ",
    "value": "CERRADO"
  },
  "then": {
    "kind": "REQUIRE",
    "column": "monto_pagado",
    "operator": "NOT_NULL"
  },
  "runtime_action": "BLOCK_LOAD"
}
```

## 8. Persistencia gobernada

SRL tendrá dos capas de almacenamiento.

### 8.1 GCS — fuente canónica de artefactos

Estructura propuesta:

```text
gs://<artifact-bucket>/silver-rules/
  language/
    srl-v1.0/
      grammar.yaml
      operators.yaml
      examples.yaml
  rules/
    <spec_id>/
      mapping-v<version>/
        rules.srl
        rules.json
        metadata.json
```

GCS conserva la representación inmutable usada para package y ejecución, incluyendo hash.

### 8.2 BigQuery — Rule Registry consultable

Tabla propuesta:

`proyectopersonal-480420.dataops_control.silver_rule_registry`

Campos mínimos:

- rule_id STRING NOT NULL
- srl_version STRING NOT NULL
- rule_family STRING NOT NULL
- srl_expression STRING NOT NULL
- ast_json STRING NOT NULL
- natural_language_example STRING
- source_columns ARRAY<STRING>
- operator STRING
- runtime_action STRING
- status STRING NOT NULL
- version INT64 NOT NULL
- workflow_id STRING
- spec_id STRING
- mapping_version INT64
- created_by STRING
- approved_by STRING
- artifact_uri STRING
- artifact_hash STRING
- interpretation_confidence FLOAT64
- accepted_without_changes BOOL
- corrected_by_user BOOL
- rejected BOOL
- created_at TIMESTAMP NOT NULL
- approved_at TIMESTAMP

Estados iniciales:

- DRAFT
- PENDING_APPROVAL
- APPROVED
- RETIRED

## 9. Language Catalog

Tabla propuesta:

`proyectopersonal-480420.dataops_control.silver_rule_language_catalog`

Contendrá la definición consultable del lenguaje:

- srl_version
- family
- keyword
- operator
- syntax_template
- parameter_contract_json
- supported_data_types
- allowed_runtime_actions
- example_srl
- example_natural_language
- status
- created_at

La IA no ampliará el lenguaje por sí misma. Solo podrá proponer constructos activos en este catálogo.

## 10. Retrieval para agentes

Tools propuestas:

- `get_srl_language_contract(family, version)`
- `find_similar_approved_rules(family, natural_text, schema)`
- `get_srl_examples(family, operator)`
- `parse_srl(srl_text)`
- `validate_srl(ast, schema)`

La fuente de verdad es BigQuery/GCS. Embeddings o búsqueda vectorial se podrán incorporar para recuperación semántica, pero nunca reemplazarán el contrato canónico.

## 11. Retrieval semántico futuro

Se podrán generar embeddings de:

- natural_language_example
- srl_expression
- interpretation
- dominio
- nombres/tipos de columnas

La similitud semántica se usará solo para recuperar ejemplos aprobados. La regla propuesta siempre debe pasar parser y validator determinísticos.

## 12. Compilación hacia runtime existente

SRL no reemplaza los contratos internos ya implementados; los alimenta.

Ejemplos:

`CHECK ramo_id NOT_NULL` -> `NOT_NULL`

`CHECK moneda IN ["PEN","USD"]` -> `ALLOWED_VALUES` + `parameters.allowed_values`

`CHECK edad BETWEEN 18 AND 100` -> `VALUE_RANGE` + `parameters.min/max`

`CHECK correo MATCHES "..."` -> `REGEX` + `parameters.pattern`

`DERIVE monto_comision = monto_reclamado * 0.10` -> `ARITHMETIC` + una source column + `parameters.operator=MULTIPLY` + `parameters.scalar=0.10`

El compiler PySpark existente sigue siendo el punto final de generación de expresión ejecutable.

## 13. UX objetivo

La pantalla de reglas debe ofrecer:

```text
Crear regla
[ Constructor visual ] [ Pseudocódigo SRL ] [ Describir con IA ]
```

Después de interpretar:

```text
Entendí tu regla así:
CHECK moneda IN ["PEN", "USD"]
ON_FAIL WARN

[ Confirmar ] [ Editar ] [ Rechazar ]
```

Los errores técnicos detallados pueden quedar disponibles en un panel de diagnóstico, pero no deben ser la respuesta principal del producto ante una interpretación fallida.

## 14. Package y ejecución

El package debe incorporar:

- versión SRL
- reglas SRL aprobadas
- AST/contrato normalizado
- hashes
- metadata de aprobación

Generar package y crear execution son decisiones separadas.

Flujo objetivo:

```text
Quality Review APPROVED
        |
        v
Generar Package
        |
        v
Package generado
[ Descargar ZIP ] [ Continuar a Dataproc ]
        |                    |
        |                    +--> crear execution -> Paso 6
        +--> descarga sin cambiar de paso
```

El botón de descarga debe continuar accesible desde el proceso/versiones aunque exista una execution.

## 15. AgentOps y métricas de interpretación

Registrar, sin inventar métricas:

- total_interpretations
- accepted_without_changes
- corrected_by_user
- rejected
- parser_failures
- validator_failures
- repair_attempts
- repair_successes

Esto permite medir precisión real de interpretación IA→SRL.

## 16. Alcance de implementación

### Fase A — SRL foundation

- modelos AST Pydantic
- parser determinístico
- validator por schema/tipo
- compiler AST -> contratos internos
- unit tests

### Fase B — CHECK

- NOT_NULL
- UNIQUE
- IN
- BETWEEN
- MATCHES
- runtime actions existentes
- Builder visual + SRL + IA

### Fase C — TRANSFORM

- COPY
- CAST
- arithmetic column/scalar
- arithmetic column/column
- CONCAT
- Builder visual + SRL + IA

### Fase D — Registry

- BigQuery language catalog
- BigQuery rule registry
- GCS canonical artifacts
- hash/version/status
- retrieval tools para agentes

### Fase E — BUSINESS

- WHEN/THEN/REQUIRE
- operadores condicionales acotados
- compilación segura
- runtime gobernado

## 17. Criterios de aceptación v1.0

1. `CHECK ramo_id NOT_NULL ON_FAIL BLOCK_LOAD` parsea y valida contra un schema que contiene ramo_id.
2. `CHECK moneda IN ["PEN","USD"] ON_FAIL WARN` compila al contrato ALLOWED_VALUES vigente.
3. `DERIVE monto_comision = monto_reclamado * 0.10` compila a ARITHMETIC con una source column y scalar.
4. Una columna inexistente es rechazada antes de persistencia.
5. Un operador no catalogado es rechazado antes de persistencia.
6. Una salida IA inválida no se ejecuta ni persiste.
7. La IA puede recuperar lenguaje y ejemplos aprobados desde el registry.
8. El usuario puede crear la misma regla sin IA mediante Builder o SRL.
9. Toda regla APPROVED conserva versión, hash, autor/aprobador y artifact_uri.
10. El ZIP contiene la versión SRL y las reglas aprobadas usadas para ejecución.
11. Generar package no crea ni lanza automáticamente una ejecución.
12. El ZIP permanece descargable después de generado.
13. El orquestador Silver actual no se modifica.

## 18. Decisiones pendientes

- nombre definitivo: Silver Rule Language (SRL) queda como nombre de trabajo.
- estrategia de búsqueda semántica: BigQuery vector search vs servicio dedicado; no bloquea v1.0.
- sintaxis exacta de BUSINESS WHEN/THEN; se cierra antes de Fase E.
- política de default para ON_FAIL cuando el usuario no la expresa; debe ser explícita por familia y gobernada, no inferida silenciosamente.
