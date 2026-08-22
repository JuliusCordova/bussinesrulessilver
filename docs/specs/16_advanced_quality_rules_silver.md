# Spec 16 — Advanced Quality Rules for Business Rules Silver

## 1. Objetivo

Evolucionar el paso 4 de Business Rules Silver desde un conjunto básico de reglas de calidad hacia un **Quality Rule Designer gobernado**, con recomendaciones basadas en profiling real, configuración avanzada, lenguaje natural, validación previa, aprobación humana, versionamiento y trazabilidad completa dentro del proceso Bronze → Silver.

Esta evolución toma como referencia funcional el módulo `quality-rules` de `enterprise-dataops-platform-ui`, pero Business Rules Silver mantendrá su propio contrato y ciclo de vida integrado al workflow Silver.

## 2. Situación actual

El agente `quality-rule-advisor` actual trabaja principalmente con evidencia derivada del profiling para proponer reglas de tipo:

- `NOT_NULL`
- `UNIQUE`
- `ALLOWED_VALUES`
- `VALUE_RANGE`
- `REGEX`

La generación automática hoy se concentra principalmente en nulos, unicidad y baja cardinalidad. El frontend también simplifica dimensión, severidad y thresholds al aprobar propuestas.

Esto resulta insuficiente para un proceso Bronze → Silver empresarial donde se requiere diseñar controles reutilizables y expresivos.

## 3. Principios de diseño

1. **No inventar reglas sin evidencia.** Las recomendaciones automáticas deben mostrar la evidencia factual utilizada.
2. **Human-in-the-loop obligatorio.** Ninguna recomendación del agente queda activa sin aprobación explícita.
3. **Separar recomendación, edición, validación y publicación.**
4. **Las reglas son parte versionada del proceso Silver.** Una modificación posterior debe crear una nueva versión y nunca sobrescribir una versión histórica aprobada.
5. **El agente interpreta; las tools validan.** Gemini puede proponer e interpretar lenguaje natural, pero la validez de columnas, tipos, parámetros y contratos ejecutables debe verificarse determinísticamente.
6. **Reglas ejecutables.** Toda regla aprobada debe poder traducirse a un contrato implementable por el notebook/job Silver.
7. **Trazabilidad.** Cada regla debe conservar su fuente, evidencia, confianza, autor/aprobador y versión.

## 4. Nueva experiencia de usuario

El paso actual `Reglas` pasa a denominarse:

**Paso 4 — Calidad & Reglas de Negocio**

La pantalla tendrá tres modos complementarios:

### 4.1 Recomendadas por IA

El agente analiza profiling, business keys, schema y contexto del proceso y propone controles con:

- regla propuesta
- dimensión de calidad
- columna(s)
- severidad
- warning threshold
- critical threshold
- parámetros
- evidencia observada
- confianza
- estado actual PASSING / FAILING / NEEDS_REVIEW
- riesgo o advertencia
- acción Aprobar / Editar / Rechazar

### 4.2 Crear regla manual

El usuario podrá crear una regla seleccionando:

- tipo
- columna o columnas
- nombre
- dimensión
- parámetros específicos
- warning threshold
- critical threshold
- severidad

### 4.3 Crear regla con IA / lenguaje natural

El usuario podrá expresar una regla en lenguaje natural o pseudo-código.

Ejemplos:

- `El importe debe ser mayor a cero excepto cuando estado sea ANULADO.`
- `fecha_fin debe ser mayor o igual a fecha_inicio.`
- `El monto total por lote no debe diferir en más de 0.5% del monto de control.`
- `El código de cliente debe existir en la tabla maestra clientes.`

El agente deberá responder primero con una **interpretación explícita**, nunca activar directamente la regla.

Ejemplo esperado:

```text
Entendí tu regla así

Nombre: importe_positivo_excepto_anulado
Tipo: CONDITIONAL_EXPRESSION
Expresión: importe > 0 OR estado = 'ANULADO'
Columnas: importe, estado
Dimensión: VALIDITY / BUSINESS
Severidad propuesta: HIGH
Schema validation:
  ✓ importe existe — NUMERIC
  ✓ estado existe — STRING
Confianza: 96%

[Editar] [Aprobar regla]
```

Si existe ambigüedad, columnas inexistentes, tipos incompatibles o una expresión no ejecutable, el agente debe responder `NEEDS_CLARIFICATION` o `BLOCKED` y no permitir aprobar.

## 5. Catálogo objetivo de reglas

El catálogo debe ser dinámico y extensible desde backend. Como baseline:

### Completeness
- `NOT_NULL`
- `NULL_RATE`
- `ROW_COUNT_MIN`
- `ROW_COUNT_RANGE`

### Uniqueness
- `UNIQUE`
- `DUPLICATE_RATE`
- `COMPOSITE_KEY_UNIQUE`

### Validity
- `VALUE_RANGE`
- `ALLOWED_VALUES`
- `REGEX`
- `TYPE_FORMAT`
- `LENGTH_RANGE`

### Consistency
- `COLUMN_COMPARISON`
- `CONDITIONAL_EXPRESSION`
- `DATE_ORDER`

### Referential Integrity
- `REFERENCE_EXISTS`
- `REFERENCE_COVERAGE`

### Timeliness
- `FRESHNESS_MAX_AGE`
- `LATE_ARRIVAL_RATE`

### Aggregate / Reconciliation
- `AGGREGATE_MIN_MAX`
- `SUM_TOLERANCE`
- `COUNT_TOLERANCE`

### Business
- `BUSINESS_EXPRESSION`
- `CUSTOM_SQL_PREDICATE` solo si se implementa con política y validación segura; no aceptar SQL arbitrario sin parser/allowlist.

## 6. Contrato canónico de QualityRule

```text
QualityRule
├── rule_id
├── rule_name
├── rule_version
├── dimension
├── rule_type
├── columns[]
├── parameters{}
├── expression
├── warning_threshold
├── critical_threshold
├── severity
├── evidence{}
├── confidence
├── source
│   ├── PROFILE
│   ├── AGENT
│   ├── USER
│   └── BUSINESS_LANGUAGE
├── current_status
├── approval_status
├── approved_by
├── approved_at
├── created_by
└── created_at
```

Estados de aprobación mínimos:

- `DRAFT`
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`
- `BLOCKED`
- `NEEDS_CLARIFICATION`

## 7. Evidencia y recomendación del agente

Las recomendaciones deben partir del profiling real y, según corresponda, de muestras de dominio controladas.

Ejemplos:

### Null rate

```text
Columna: fecha_nacimiento
Nulls: 8,312
Rows: 1,020,000
Null rate: 0.815%

Propuesta:
NULL_RATE <= 0.1%
Dimensión: COMPLETENESS
Severidad: HIGH
Confianza: 94%
```

### Allowed values

```text
Columna: estado_cliente
Distinct values observados: 4
Valores: ACTIVO, INACTIVO, BLOQUEADO, BAJA

Propuesta:
ALLOWED_VALUES = [...]
Dimensión: VALIDITY
Confianza: 91%
```

La evidencia mostrada al usuario debe ser la misma evidencia registrada en el contrato de la regla.

## 8. Thresholds

Cada tipo que corresponda debe soportar dos niveles:

- `warning_threshold`
- `critical_threshold`

La UI debe permitir editarlos antes de la aprobación.

Los defaults pueden ser propuestos por el agente, pero deben distinguirse visualmente como recomendación y no como política corporativa.

## 9. Severidad

Valores iniciales:

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

El agente puede recomendar severidad según:

- business key
- campo crítico
- sensibilidad de la regla para el proceso Silver
- estado actual observado
- impacto potencial sobre carga o consumo downstream

Pero el usuario puede modificarla antes de aprobar.

## 10. Draft → Validate → Approve

Se adopta el patrón útil identificado en `enterprise-dataops-platform-ui`:

1. Diseñar / editar reglas.
2. Guardar borrador.
3. Validar configuración contra backend.
4. Resolver findings.
5. Aprobar/publicar dentro del workflow Silver.

Una modificación posterior a una versión aprobada genera una nueva versión de Quality Rules.

## 11. Validaciones determinísticas mínimas

Antes de permitir aprobación:

- todas las columnas existen en el schema efectivo
- los tipos son compatibles con el rule type
- parámetros obligatorios presentes
- thresholds coherentes
- warning <= critical cuando la semántica lo requiera
- valores permitidos no vacíos
- min <= max
- referencias externas tienen tabla/columna destino válidas
- expresiones condicionales compilan al DSL/AST soportado
- no se permite SQL arbitrario sin una política explícita

## 12. Lenguaje natural: arquitectura

Flujo:

```text
Usuario
  → intención en lenguaje natural / pseudo-código
  → quality-rule-advisor
  → interpretación estructurada
  → validator determinístico
  → resultado
      APPROVABLE
      NEEDS_CLARIFICATION
      BLOCKED
  → aprobación humana
  → QualityRule versionada
```

El LLM no debe ser la última autoridad de validación.

## 13. Integración con el proceso Bronze → Silver

El proceso versionado queda compuesto por:

```text
Silver Process
├── workflow_version
├── mapping_version
├── quality_rules_version
├── spec_version
├── package_version
└── executions[]
```

Una regla aprobada debe propagarse al `specification.json`, `manifest.json`, notebook/job Silver y evidencia de ejecución correspondiente.

## 14. Quality Gates en runtime

Las reglas deberán clasificarse además por comportamiento de ejecución:

- `OBSERVE_ONLY`
- `WARN`
- `QUARANTINE`
- `BLOCK_LOAD`

Ejemplo:

- regla HIGH con threshold warning → `WARN`
- regla CRITICAL superando critical threshold → `BLOCK_LOAD`
- regla configurable para enviar registros inválidos a cuarentena → `QUARANTINE`

La política exacta debe ser aprobada como parte del proceso y no inferida silenciosamente por el agente.

## 15. UX sugerida

Cada tarjeta de regla debe mostrar:

```text
[✓] importe_positivo_excepto_anulado     IA · 96%

BUSINESS / VALIDITY     HIGH

importe > 0 OR estado = 'ANULADO'

Columnas: importe, estado
Warning: 0.1%   Critical: 1.0%
Estado observado: PASSING

Evidencia
- importe NUMERIC
- estado STRING
- 0.03% de filas incumplen actualmente

[Editar] [Aprobar] [Rechazar]
```

Panel derecho `Gemini Quality Advisor`:

- cobertura por dimensión
- campos críticos sin regla
- reglas redundantes
- reglas incompatibles
- riesgos
- recomendaciones adicionales

## 16. Diferencias frente al agente actual

El agente actual no debe eliminarse; debe evolucionar.

### Actual
- profiling → NOT_NULL / UNIQUE / dominios simples
- propuestas puntuales
- parámetros y thresholds limitados

### Objetivo
- catálogo dinámico
- reglas multi-columna
- reglas condicionales
- referencias
- freshness
- agregados
- thresholds editables
- severidad gobernada
- drafts
- validación backend
- lenguaje natural
- evidencia + confianza
- versionamiento
- quality gates ejecutables

## 17. Criterios de aceptación

1. El usuario puede consultar el catálogo de tipos soportados.
2. Puede crear y editar reglas manualmente.
3. Puede configurar warning/critical thresholds cuando aplique.
4. Puede guardar una configuración como draft y recuperarla.
5. Puede validar el draft antes de aprobarlo.
6. Las recomendaciones de IA muestran evidencia y confidence.
7. Puede crear una regla en lenguaje natural.
8. La interpretación de lenguaje natural se valida contra schema y contrato ejecutable.
9. Una interpretación ambigua no puede aprobarse.
10. Ninguna regla generada por IA se activa sin aprobación humana.
11. Las reglas aprobadas tienen versión propia.
12. Modificar reglas aprobadas crea una nueva versión.
13. El package Silver registra `quality_rules_version`.
14. La ejecución registra qué versión de reglas utilizó.
15. Las reglas aprobadas aparecen en la especificación y artefactos generados.
16. Los quality gates ejecutables respetan la política aprobada.

## 18. Orden recomendado de implementación

### Fase A — Contrato y catálogo
- contrato `QualityRule`
- catálogo dinámico
- tipos/parameters/thresholds
- tests determinísticos

### Fase B — Designer
- tarjetas de regla
- alta/edición/borrado
- draft / recover / validate
- panel de cobertura

### Fase C — Agente avanzado
- recomendaciones por profiling
- evidence/confidence
- cobertura de dimensiones

### Fase D — Lenguaje natural
- parser asistido por Gemini
- salida estructurada
- validator determinístico
- clarification flow

### Fase E — Versionamiento y runtime
- `quality_rules_version`
- integración spec/package
- quality gates
- evidencia AgentOps

## 19. Decisión de producto

Business Rules Silver no reutilizará directamente el frontend ni el backend del módulo Quality Rules de Enterprise DataOps. Se reutiliza el **patrón conceptual**: catálogo + diseñador + draft + validate + publish, extendido para el ciclo de vida Bronze → Silver, agentes Gemini ADK, lenguaje natural, versionamiento y ejecución gobernada.
