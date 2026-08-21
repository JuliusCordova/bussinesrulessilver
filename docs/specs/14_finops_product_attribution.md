# FinOps por producto — Business Rules Silver

## Objetivo

Construir una capa de FinOps que permita determinar el costo de `BUSINESS_RULES_SILVER` sin confundir costo facturado con costo atribuido.

## Principio canónico

La solución debe separar tres conceptos:

1. **FACTURADO**: costo real proveniente de Google Cloud Billing Export.
2. **ATRIBUIDO_DIRECTO**: costo facturado asociado de forma inequívoca a recursos exclusivos del producto.
3. **ATRIBUIDO_COMPARTIDO**: costo facturado de recursos compartidos distribuido mediante una regla explícita, versionada y auditable.

Nunca se debe presentar un costo atribuido como si fuera facturación directa de Google.

## Producto canónico

`BUSINESS_RULES_SILVER`

## Fuente de verdad financiera

Dataset:

`proyectopersonal-480420.cloud_billing_export`

Tabla detallada observada:

`gcp_billing_export_resource_v1_018A15_4691E8_C0A72F`

La moneda de facturación observada es `PEN`. El costo normalizado en USD debe calcularse usando el `currency_conversion_rate` contenido en el propio Billing Export.

## Fuentes complementarias

- `agentops.fact_llm_calls`
- `dataops_control.silver_agent_governance_runs`
- inventario de Cloud Run
- inventario de BigQuery
- labels/tags de recursos GCP cuando existan
- resource.name / resource.global_name del Detailed Billing Export cuando estén disponibles

## Modelo objetivo

### 1. Catálogo de atribución

Tabla propuesta:

`dataops_control.finops_resource_attribution`

Campos mínimos:

- `product_id`
- `gcp_service`
- `resource_pattern`
- `resource_type`
- `component`
- `allocation_type`
- `allocation_rule`
- `effective_from`
- `effective_to`
- `is_active`
- `evidence`

Valores de `allocation_type`:

- `DIRECT`
- `SHARED`
- `UNATTRIBUTED`

### 2. Costo diario por producto

Vista propuesta:

`dataops_control.silver_finops_product_daily`

Debe exponer como mínimo:

- `usage_date`
- `product_id`
- `cost_category` (`AI`, `INFRA`, `OTHER`)
- `service`
- `gross_cost_billing_currency`
- `credits_billing_currency`
- `net_cost_billing_currency`
- `billing_currency`
- `gross_cost_usd`
- `credits_usd`
- `net_cost_usd`
- `allocation_type`
- `allocation_factor`
- `cost_semantics`
- `evidence`

## Regla de atribución inicial

### Recursos directos de Business Rules Silver

Se consideran candidatos a `DIRECT` únicamente cuando la evidencia de Billing o inventario permite identificar inequívocamente el recurso. Ejemplos a validar:

- Cloud Run `silver-refinement-agent`
- Cloud Run `business-rules-silver-ui`
- Cloud Run `business-rules-silver-governance-preview` solo para ambiente preview, no producción
- recursos con labels/tags explícitos `product=business-rules-silver`

No se debe inferir atribución directa solamente por el nombre del servicio GCP (`Cloud Run`, `BigQuery`, etc.).

### Vertex AI

El costo de Vertex AI facturado a nivel proyecto se mantiene como `FACTURADO`.

Para asignarlo internamente a agentes/runs de Silver, la primera aproximación será proporcional al consumo real de tokens observado en `agentops.fact_llm_calls`, filtrando los agentes Silver canónicos.

La salida por agente/run debe etiquetarse `ATRIBUIDO` y registrar la regla de reparto.

### BigQuery, Storage, Logging, Networking y otros

Solo se clasificarán como `DIRECT` si el Detailed Billing Export expone un recurso, label o identificador que permita vincular el cargo al producto. En caso contrario se mantendrán como `SHARED` o `UNATTRIBUTED` hasta definir una regla defendible.

## Taxonomía de costo

- `AI`: Vertex AI / Gemini u otros consumos de IA claramente identificados.
- `INFRA`: Cloud Run, BigQuery, Cloud Storage, Artifact Registry, Networking, Logging u otros servicios de plataforma.
- `OTHER`: cargos no clasificables dentro de los dos anteriores.

## KPIs objetivo del dashboard

- costo facturado del proyecto
- costo atribuible a Business Rules Silver
- porcentaje del costo del proyecto atribuible a Silver
- costo AI Silver
- costo infraestructura Silver
- costo promedio por run
- costo atribuido por agente
- agente más costoso
- costo diario AI vs Infra vs Total
- costos no atribuibles / cobertura de atribución

## Métricas de calidad de atribución

El dashboard debe mostrar también:

- `% costo DIRECT`
- `% costo SHARED atribuido`
- `% costo UNATTRIBUTED`

Esto permite saber cuán confiable es el costo por producto y evita una falsa precisión.

## Labels objetivo para despliegues futuros

Siempre que el recurso GCP lo soporte:

- `product=business-rules-silver`
- `domain=dataops`
- `environment=prod|preview|test`
- `component=backend|frontend|governance|data`
- `cost_center=dataops`

Los labels mejoran la atribución futura, pero no deben aplicarse retroactivamente a costos históricos sin evidencia.

## Secuencia de implementación

1. Descubrir qué campos de `resource`, `labels`, `system_labels` y `tags` están realmente poblados en Billing Export.
2. Identificar recursos Silver de forma inequívoca.
3. Crear catálogo de atribución versionado.
4. Crear costo diario por producto.
5. Exponer endpoint `/agentops/finops/product`.
6. Incorporar UI de costo producto + cobertura de atribución.
7. Implementar atribución Vertex AI por agente/run usando telemetría real.
8. Validar candidato y preview antes de cualquier promoción a producción.

## Gate de calidad

No se acepta un valor de costo por producto si:

- proviene de precios sintéticos;
- no se puede rastrear a Billing Export;
- un costo compartido se presenta como directo;
- la moneda se etiqueta incorrectamente;
- no se expone la semántica `FACTURADO` o `ATRIBUIDO`;
- no existe evidencia de la regla de asignación.
