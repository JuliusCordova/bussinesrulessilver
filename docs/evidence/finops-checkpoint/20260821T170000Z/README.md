# FinOps checkpoint — 2026-08-21

## Branch
`feat/finops-real-preview`

## Estado validado
- Backend candidato FinOps Billing-aware: **SUCCESS**.
- Cloud Build validado: `7b2f8135-ae86-43ef-b5d5-160fe955eb9f`.
- Evidencia previa del candidato: `docs/evidence/finops-candidate/20260821T162434Z/README.md`.
- Preview desplegado y smoke validado.
- Revisión activa del preview: `business-rules-silver-governance-preview-00006-fml`.
- Preview sirve 100% del tráfico.
- URL: `https://business-rules-silver-governance-preview-913797829604.us-central1.run.app`.

## FinOps implementado
- Telemetría real Gemini ADK por agente/run.
- Correlación de `trace_id` con governance `run_id`.
- Endpoints existentes: `/agentops/finops/summary`, `/daily`, `/agents`, `/runs`.
- Endpoint Billing-aware `/agentops/finops/services` preparado.
- Frontend preparado para mostrar consumo real y USD únicamente cuando Cloud Billing Export tenga datos.
- No se calculan ni muestran costos sintéticos.
- Semántica conservada: Facturado / Atribuido / No atribuible.

## Cloud Billing Export
- Proyecto: `proyectopersonal-480420`.
- Billing account: `018A15-4691E8-C0A72F`.
- Dataset: `proyectopersonal-480420.cloud_billing_export`.
- Location: `US`.
- Detailed Billing Export: **habilitado**.
- Pricing Export: **habilitado en UI**.
- FOCUS: deshabilitado.
- Standard: deshabilitado.
- Dataset confirmado existente.
- Última comprobación: `bq ls --project_id=proyectopersonal-480420 cloud_billing_export` devolvió **0 tablas**.
- La primera materialización de `gcp_billing_export_resource_v1_*` sigue pendiente.
- Por lo tanto, USD facturados reales aún no están disponibles.

## Próximo checkpoint
Ejecutar:

```bash
bq ls \
  --project_id=proyectopersonal-480420 \
  cloud_billing_export
```

Cuando aparezca `gcp_billing_export_resource_v1_*`:
1. inspeccionar nombre y schema reales;
2. validar `cost`, `credits`, `currency`, `usage_start_time`, `service`, `sku`;
3. consultar gross/credits/net cost real;
4. validar `/agentops/finops/services`;
5. habilitar visualización USD real en preview;
6. mantener separado costo facturado del proyecto vs costo atribuido a Silver/agente/run.

## Hallazgo de arquitectura agéntica
Se identificó que el catálogo registra 6 agentes/capacidades ADK, pero el journey UI actual invoca directamente principalmente `table-profiler`, `mapping-advisor` y `quality-rule-advisor`; el resto del flujo contiene capacidades determinísticas y un orquestador disponible. Este hallazgo se mantiene como **backlog de mejora futura** y no se modificará en la fase FinOps actual.
