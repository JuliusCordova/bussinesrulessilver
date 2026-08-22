# Spec 17 — Business Rules Silver · Product Evolution Execution Plan

Fecha: 2026-08-21
Estado: APPROVED FOR IMPLEMENTATION
Branch: `feat/silver-processes-packages`

## Objetivo

Evolucionar Business Rules Silver desde un wizard gobernado Bronze → Silver hacia un producto reutilizable de Agentic DataOps que permita crear, consultar, editar, versionar, empaquetar y operar procesos Silver con trazabilidad de extremo a extremo.

Esta evolución preserva dos principios:

1. La IA recomienda e interpreta; las decisiones relevantes siguen sujetas a aprobación humana.
2. Un artefacto ejecutado debe ser exactamente el artefacto versionado y trazable que fue aprobado.

El agente orquestador existente queda fuera del alcance de esta evolución. No se modifica ni se conecta al flujo actual hasta que exista un caso de uso que justifique ese esfuerzo.

---

## Baseline existente reutilizable

El backend ya expone capacidades útiles que deben reutilizarse antes de crear nuevas APIs:

- `GET /silver-workflows` — lista workflows persistidos.
- `GET /silver-workflows/{workflow_id}` — recupera un workflow.
- `POST /silver-workflows/{workflow_id}/mapping-recommendations`.
- gestión de Business Rules draft/generate/confirm.
- persistencia de Specification y Quality Review.
- generación y listado de artefactos.
- descarga individual de artefactos.
- creación/validación/ejecución de packages.

`SilverWorkflowRecord` ya contiene, entre otros:

- `workflow_id`
- `version`
- `status`
- `source`
- `mapping_rules`
- `mapping_version`
- `silver_target`
- `quality_rules`
- `artifact_package`
- `spec_id`
- `execution_id`
- `created_by`
- `created_at`
- `updated_at`
- `metadata`

El frontend actual no expone toda esta riqueza al usuario.

---

# Roadmap de implementación

## Fase 1 — Procesos Silver

### Objetivo
Convertir workflows existentes en activos visibles y recuperables.

### UX
Nueva entrada principal: **Procesos Silver**.

Tabla/catálogo mínimo:

| Campo | Descripción |
|---|---|
| Proceso | Nombre amigable / workflow_id |
| Origen | project.dataset.table Bronze |
| Destino | project.dataset.table Silver |
| Estado | DRAFT / APPROVED / EXECUTING / SUCCEEDED / etc. |
| Workflow version | versión actual |
| Mapping version | versión actual |
| Spec | spec_id |
| Última actualización | updated_at |
| Responsable | created_by / metadata owner |

Acciones:

- Abrir
- Continuar edición
- Ver detalle
- Ver versiones
- Ver ejecuciones

### Reglas

- Abrir un proceso debe hidratar el wizard desde backend.
- No depender de estado local del navegador para reconstruir el proceso.
- Editar una versión aprobada nunca debe destruir evidencia histórica.

### Criterios de aceptación

- El usuario puede listar workflows reales persistidos.
- Puede abrir al menos un workflow existente.
- Source/target/version/status provienen del backend.
- No hay datos mock para procesos.

---

## Fase 2 — Package & Versiones

### Objetivo
Hacer visible la cadena de versionamiento y storage que ya forma parte del contrato técnico.

### UX
Renombrar el Paso 5 de **Artefactos** a **Package & Versiones**.

Header de identidad:

- Workflow vN
- Mapping vN
- Quality Rules vN cuando esté disponible
- Spec
- Package vN
- estado de package
- `artifact_package_uri`

Cada artefacto debe mostrar:

- artifact type
- artifact name
- artifact version
- validation status
- storage URI
- content hash
- acción Descargar

### Package ZIP

Agregar descarga del package completo gobernado.

El ZIP descargado debe corresponder al package persistido/versionado en Storage; no debe reconstruirse de forma independiente en el navegador.

Contenido objetivo:

```text
business_rules_silver_vN/
├── README.md
├── manifest.json
├── specification.json
├── mapping.json
├── silver_ddl.sql
├── silver_notebook.ipynb
├── silver_job.py
└── metadata/
    ├── artifact_hashes.json
    └── package_metadata.json
```

### Criterios de aceptación

- Versiones y URIs reales visibles.
- Hash real visible cuando exista.
- Artefactos descargables individualmente.
- Package completo descargable como ZIP.
- El ZIP descargado es el package que el backend valida/ejecuta.

---

## Fase 3 — Mapping inteligente en lenguaje natural

Basado en Spec 15.

### Modos de columna

1. DIRECT
2. TRANSFORMATION
3. DERIVED_NL

### DERIVED_NL

El usuario puede escribir lenguaje natural o pseudocódigo, por ejemplo:

- `margen = venta - costo`
- `importe_neto = importe_total - descuento; si descuento es null usar 0`
- `si tipo_cliente es VIP y saldo > 100000 crear segmento PREMIUM`

El `mapping-advisor` debe:

1. interpretar la intención;
2. resolver columnas contra schema real;
3. validar tipos;
4. generar una representación técnica estructurada;
5. explicar su interpretación;
6. declarar confianza y riesgos;
7. detenerse si existe ambigüedad;
8. exigir aprobación humana antes de incorporar el campo al mapping.

Estados de interpretación:

- VALIDATED
- NEEDS_CLARIFICATION
- BLOCKED

No se ejecuta código arbitrario generado por el LLM.

---

## Fase 4 — Advanced Quality Rules

Basado en Spec 16 y en el patrón probado de `enterprise-dataops-platform-ui`.

Capacidades:

- catálogo dinámico de rule types;
- reglas recomendadas y manuales;
- warning threshold;
- critical threshold;
- severidad;
- parámetros por tipo;
- draft → validate → approve;
- reglas multicolumna;
- reglas en lenguaje natural;
- evidencia proveniente del profiling;
- aprobación humana;
- versionamiento de Quality Rules.

Dimensiones objetivo:

- COMPLETENESS
- UNIQUENESS
- VALIDITY
- CONSISTENCY
- REFERENTIAL_INTEGRITY
- TIMELINESS
- AGGREGATE
- BUSINESS

Quality gates objetivo:

- OBSERVE_ONLY
- WARN
- QUARANTINE
- BLOCK_LOAD

---

## Fase 5 — Impact Analysis y comparación de versiones

Cuando cambie Mapping o Quality Rules:

- mostrar diff;
- identificar columnas afectadas;
- identificar reglas afectadas;
- marcar Specification como STALE cuando corresponda;
- marcar Package como STALE cuando corresponda;
- exigir regeneración antes de ejecutar una versión obsoleta.

Ejemplo de experiencia:

```text
Mapping v4 → v5
2 columnas modificadas
1 campo derivado nuevo
3 Quality Rules afectadas
1 regla requiere revalidación
DDL cambia
Notebook cambia
Package requiere regeneración
Riesgo: MEDIO
```

---

## Fase 6 — Operación y Gobierno

Integrar los procesos con las vistas de gobierno ya existentes:

- procesos activos;
- ejecuciones por proceso;
- calidad histórica;
- versiones productivas;
- agentes que intervinieron;
- usuario que aprobó;
- evidencia de decisiones;
- FinOps por proceso cuando exista atribución defensible.

No se inventarán costos ni atribuciones.

---

# Orden de implementación acordado

1. Procesos Silver — catálogo + abrir workflow.
2. Package & Versiones — exposición de versiones/storage/hash.
3. ZIP gobernado.
4. Mapping DERIVED_NL.
5. Advanced Quality Rules.
6. Impact Analysis / diff.
7. Gobierno operativo y métricas por proceso.

---

# Fuera de alcance por ahora

## Agente orquestador

El `silver_design_orchestrator` existente no se modifica.

Razón:

- no participa actualmente en el flujo real de UI;
- el flujo actual tiene human approval gates explícitos;
- evolucionarlo a un agente de routing/state-aware tiene costo arquitectónico sin beneficio inmediato frente a las prioridades actuales.

Se mantiene como backlog.

---

# Primera iteración técnica

La Iteración 1 debe reutilizar `GET /silver-workflows` y `GET /silver-workflows/{workflow_id}` para construir el catálogo de Procesos Silver y evitar crear APIs redundantes.

Antes de ampliar backend, se debe demostrar qué información real ya puede obtenerse con el contrato existente.
