# 15 — Procesos Bronze → Silver gobernados, Mapping en lenguaje natural y Packages versionados

Fecha: 2026-08-21
Rama: `feat/finops-real-preview`
Producto: Business Rules Silver
Estado: ESPECIFICACIÓN FUNCIONAL APROBADA PARA DISEÑO

## 1. Objetivo

Evolucionar Business Rules Silver desde un wizard de generación puntual hacia un **catálogo gobernado de procesos de carga Bronze → Silver**, donde cada proceso pueda:

- crearse;
- consultarse posteriormente;
- reabrirse;
- editarse de forma controlada;
- versionarse;
- regenerar artefactos;
- conservar historial y trazabilidad;
- descargarse como package ejecutable/versionado.

Además, el Paso Mapping debe permitir que un usuario de negocio/data engineer defina **campos derivados en pseudo-código o lenguaje natural**, con interpretación y validación asistida por el agente `mapping-advisor` antes de incorporar la transformación al mapping.

---

## 2. Concepto de producto: Proceso Silver

Un **Proceso Silver** representa una definición gobernada y versionada de refinamiento Bronze → Silver.

Identidad mínima visible:

- `workflow_id`
- nombre funcional del proceso
- source project/dataset/table
- target project/dataset/table
- workflow version
- mapping version
- specification version / `spec_id`
- package version
- status
- owner / requested_by
- created_at
- updated_at
- último execution status
- URI de storage vigente

El usuario debe poder entrar a una vista tipo **Procesos Silver** y ver los procesos creados previamente.

### Acciones por proceso

- Abrir
- Editar
- Ver versiones
- Ver mapping
- Ver reglas
- Ver artefactos
- Descargar package
- Ver ejecuciones
- Duplicar como nuevo proceso (futuro)
- Desactivar/archivar (futuro)

### Regla de edición

Editar un proceso **no sobrescribe silenciosamente** una versión ejecutada/aprobada.

Una edición material debe generar una nueva versión de workflow/mapping/spec/package según corresponda.

---

## 3. Mapping: tres formas de definir una columna

En Paso 3 — Mapping, cada fila/columna destino puede ser de uno de estos modos:

1. `DIRECT`
   - columna origen → columna destino
   - sin transformación funcional

2. `DETERMINISTIC`
   - transformación estructurada conocida
   - cast, trim, upper/lower, concat, coalesce, date conversion, etc.

3. `DERIVED_NL`
   - campo derivado solicitado en pseudo-código o lenguaje natural
   - interpretación obligatoria por `mapping-advisor`
   - aprobación humana antes de guardar

---

## 4. UX aprobada para agregar un campo derivado

Al presionar **Agregar columna**, el usuario debe poder elegir:

- Campo directo
- Transformación guiada
- Campo derivado con IA

### Campo derivado con IA

Formulario mínimo:

- Nombre columna destino
- Tipo destino esperado (opcional / sugerible)
- Expresión en lenguaje natural o pseudo-código

Ejemplos:

> `importe_neto = importe_total - descuento; si descuento es null usar 0`

> `Clasificar como PREMIUM cuando ventas_12m > 100000, de lo contrario STANDARD`

> `fecha_operacion = convertir created_at a fecha en zona horaria America/Lima`

Botón:

**Interpretar y validar con IA**

---

## 5. Responsabilidad del agente mapping-advisor

El `mapping-advisor` NO debe aplicar directamente la expresión libre.

Debe ejecutar el siguiente ciclo:

### 5.1 Validación semántica

Determinar si entiende suficientemente la intención.

Salida requerida:

- `understood: true|false`
- `confidence`
- `ambiguities[]`
- `clarification_question` cuando sea necesario

Si `understood=false`, la transformación NO puede aprobarse.

### 5.2 Validación contra schema

Debe validar que:

- las columnas referenciadas existan en el schema origen o en campos derivados anteriores permitidos;
- los tipos sean compatibles;
- la columna destino no colisione con otra columna;
- la expresión no use campos inexistentes;
- no haya dependencia circular;
- la transformación sea soportable por el motor objetivo.

### 5.3 Traducción a contrato estructurado

Nunca guardar solo el texto natural.

El agente debe devolver una propuesta estructurada, por ejemplo:

```json
{
  "target_column": "importe_neto",
  "target_type": "NUMERIC",
  "source_columns": ["importe_total", "descuento"],
  "transformation": {
    "type": "EXPRESSION",
    "expression_language": "SQL",
    "expression": "importe_total - COALESCE(descuento, 0)"
  },
  "natural_language_source": "importe_neto = importe_total - descuento; si descuento es null usar 0",
  "understood": true,
  "confidence": 0.97,
  "risk": "LOW",
  "requires_approval": true
}
```

### 5.4 Vista de confirmación humana

La UI debe mostrar:

**Entendí tu regla así**

- Campo destino
- Campos utilizados
- Tipo resultante
- Expresión técnica propuesta
- Explicación simple
- Confianza
- Riesgos/advertencias

Acciones:

- Aprobar transformación
- Editar solicitud
- Reinterpretar
- Cancelar

Solo luego de aprobar se incorpora al mapping.

---

## 6. Diferencia Mapping vs Reglas de negocio/calidad

Debe preservarse la separación conceptual:

### Mapping
Produce o transforma datos.

Ejemplo:

`margen = venta - costo`

### Regla
Valida una condición sobre los datos.

Ejemplo:

`margen no debe ser negativo`

Si el usuario escribe una intención que parece una validación dentro del creador de campo derivado, el agente puede advertir:

> “Esto parece una regla de validación y no una transformación. ¿Deseas enviarla al paso Reglas?”

No mover automáticamente sin confirmación.

---

## 7. Versionamiento visible

El versionamiento no debe permanecer oculto en contratos técnicos.

### Encabezado del proceso

Mostrar siempre:

- Workflow vN
- Mapping vN
- Spec vN / spec_id
- Package vN

### Artefactos

Cada artefacto debe mostrar:

- tipo
- nombre
- artifact version
- CURRENT / SUPERSEDED
- generation status
- validation status
- storage URI
- content hash
- generated_at si existe

Ejemplo visual:

```text
Silver DDL
v3 · CURRENT
gs://.../workflow-123/package-v3/silver_ddl.sql
SHA-256: a83f...91c2
[Ver] [Descargar]
```

---

## 8. Historial de versiones

Debe existir una acción **Ver historial de versiones**.

Vista esperada:

| Versión | Artefacto | Estado | Hash | Storage | Acción |
|---|---|---|---|---|---|
| v3 | Notebook | CURRENT | 91ad… | gs://…/v3/ | Descargar |
| v2 | Notebook | SUPERSEDED | 4bc2… | gs://…/v2/ | Descargar |
| v1 | Notebook | SUPERSEDED | 842e… | gs://…/v1/ | Descargar |

El mismo principio debe aplicarse al package completo.

---

## 9. Storage visible

El usuario debe poder identificar dónde vive el artefacto gobernado.

No es necesario exponer secretos ni signed URLs permanentes.

Mostrar como dato de trazabilidad:

- bucket lógico / URI GCS
- ruta package vigente
- versión
- hash

El acceso/descarga debe realizarse a través del backend autorizado.

---

## 10. Package ZIP gobernado

Debe existir un botón principal:

**Descargar package Silver vN (.zip)**

Regla crítica:

> El ZIP descargado debe corresponder al mismo package versionado almacenado en Storage y utilizado para validación/ejecución. No debe reconstruirse de forma independiente en el navegador.

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

`package_metadata.json` debe incluir, cuando exista:

- workflow_id
- workflow_version
- mapping_version
- spec_id
- package_version
- source_table
- target_table
- generated_at
- generated_by
- storage_uri
- package_hash

---

## 11. Vista Procesos Silver

Nueva capacidad funcional prioritaria.

El usuario debe poder ver los procesos previamente creados.

Columnas sugeridas:

- Nombre
- Origen
- Destino
- Estado
- Workflow version
- Mapping version
- Package version
- Última ejecución
- Actualizado por
- Actualizado en

Acciones:

- Abrir
- Editar
- Descargar último package
- Versiones
- Ejecuciones

Filtros:

- origen/destino
- estado
- owner
- fecha

---

## 12. Edición gobernada de un proceso

Al abrir un proceso existente, el wizard debe hidratarse desde backend, no desde seed/local state.

El usuario puede navegar por:

- Origen/destino
- Incrementalidad
- Mapping
- Reglas
- Package & Versiones
- Ejecuciones
- Gobierno

Una modificación debe indicar visualmente:

**Cambios no publicados**

Antes de regenerar artefactos debe mostrarse el impacto:

- mapping cambia v3 → v4
- spec cambia v5 → v6
- package será v7
- versión anterior permanece inmutable

---

## 13. Criterios de aceptación

### AC-01 — Crear campo derivado
El usuario puede seleccionar “Campo derivado con IA” al agregar una columna.

### AC-02 — Lenguaje natural/pseudo-código
El usuario puede ingresar una expresión libre sin escribir SQL/PySpark obligatorio.

### AC-03 — Validación por mapping-advisor
La expresión se envía al mapping-advisor y el agente devuelve entendimiento, columnas involucradas, expresión estructurada, confianza y riesgos.

### AC-04 — No aplicación automática
La transformación no entra al mapping hasta que el usuario la aprueba.

### AC-05 — Ambigüedad
Si el agente no entiende suficientemente, la UI solicita aclaración y no permite aprobar.

### AC-06 — Schema real
No se puede aprobar una expresión que referencia columnas inexistentes sin una resolución explícita.

### AC-07 — Persistencia
La transformación aprobada queda persistida dentro de la versión de mapping, incluyendo su texto natural original y expresión técnica resultante.

### AC-08 — Procesos existentes
Existe una vista para listar procesos Silver creados previamente.

### AC-09 — Reapertura
Un proceso puede abrirse posteriormente conservando workflow/mapping/spec/package versions.

### AC-10 — Edición versionada
Editar un proceso aprobado/ejecutado genera nuevas versiones; no destruye el estado anterior.

### AC-11 — Storage visible
Los artefactos muestran su `storage_uri` y versión vigente.

### AC-12 — Hash visible
Los artefactos muestran `content_hash` cuando esté disponible.

### AC-13 — Historial
El usuario puede consultar versiones anteriores de artefactos/packages.

### AC-14 — ZIP
El usuario puede descargar el package completo como ZIP desde backend.

### AC-15 — Identidad del ZIP
El ZIP descargado corresponde al package versionado almacenado y validado, no a una reconstrucción client-side.

### AC-16 — Artefactos individuales
Se mantiene la descarga individual de DDL, Notebook, PySpark y demás artefactos disponibles.

---

## 14. Principios de gobierno

1. IA propone; humano aprueba.
2. Lenguaje natural nunca reemplaza el contrato estructurado persistido.
3. Versiones ejecutadas/aprobadas son inmutables.
4. Storage y hash forman parte de la evidencia de gobierno.
5. Package descargado = package gobernado.
6. Ningún cambio de mapping debe alterar retrospectivamente ejecuciones históricas.
7. La trazabilidad debe permitir reconstruir qué workflow/mapping/spec/package produjo una ejecución.

---

## 15. Secuencia recomendada de implementación

### Fase A — Catálogo y package gobernado
1. Listado de Procesos Silver.
2. Reapertura/hidratación de workflow existente.
3. Versiones visibles de workflow/mapping/spec/package.
4. Storage URI + hash visibles.
5. Historial de artefactos/package.
6. Endpoint de descarga ZIP completo.

### Fase B — Mapping natural-language
1. Contrato `DERIVED_NL`.
2. Endpoint/uso gobernado de `mapping-advisor` para interpretación.
3. Validación schema + tipos + dependencias.
4. UI “Entendí tu regla así”.
5. aprobación/rechazo/reinterpretación.
6. persistencia del texto natural + expresión estructurada.

### Fase C — Edición e impacto
1. Editar proceso existente.
2. detección de cambios.
3. preview de incremento de versiones.
4. regeneración controlada de spec/package.
5. trazabilidad completa ejecución → package → spec → mapping → workflow.

---

## 16. Decisión de producto

El Paso 5 debe evolucionar visualmente de **Artefactos** hacia **Package & Versiones**.

Business Rules Silver debe dejar claro que no solo genera código: crea y gobierna **procesos de refinamiento Bronze → Silver reutilizables, editables, versionados, trazables y ejecutables**.
