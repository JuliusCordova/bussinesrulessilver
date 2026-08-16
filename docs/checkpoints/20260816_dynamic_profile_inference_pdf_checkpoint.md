# Correcciones de catalogo, perfil e inferencia - 2026-08-16

## Estado

Implementado en `main` y pendiente de construir/desplegar como candidato antes de promover a produccion.

## Problemas corregidos

1. La tabla destino Silver ahora usa un control hibrido:
   - selector explicito de tablas existentes del dataset Silver;
   - opcion para escribir un nombre nuevo.
2. El schema mostrado se obtiene de la tabla Bronze seleccionada:
   - soporta el contrato real del backend (`schema` como lista);
   - normaliza `data_type` a `type`;
   - invalida el schema anterior al cambiar tabla;
   - recarga automaticamente el detalle de la nueva tabla.
3. La estrategia deja de conservar valores de `cat_producto`:
   - el perfil BigQuery reemplaza schema, business key, watermark y metrica;
   - si no existe clave candidata segura, propone `FULL`;
   - `MERGE` solo se propone automaticamente con una clave sin nulos y unicidad compatible;
   - todos los campos son editables y una modificacion queda marcada como decision humana.
4. La validacion verde ahora explica su evidencia:
   - identidad exacta de la tabla perfilada;
   - consistencia entre estrategia y business key;
   - compatibilidad temporal del watermark;
   - compatibilidad numerica de la metrica.
5. Se agrego un informe PDF gobernado:
   - endpoint `POST /silver-agents/table-profiler/report`;
   - perfil fresco consultado en BigQuery;
   - resumen, inferencia y detalle por columna;
   - visor embebido y descarga desde el wizard.

## Principio de seguridad

El PDF y la inferencia operativa se construyen desde evidencia canonica BigQuery. La salida narrativa del modelo no se usa como fuente de metricas. Toda edicion o recomendacion requiere confirmacion humana.

## Verificacion local

- Frontend: `tsc -b` conforme.
- Frontend: `vite build` conforme (19 modulos).
- PDF: encabezado `%PDF-`, A4 horizontal, una pagina de muestra renderizada con Poppler y revisada visualmente.
- Backend: modulo PDF compila y prueba de generacion valida contenido no vacio.

## Archivos principales

- `src/App.tsx`
- `src/api.ts`
- `src/types.ts`
- `src/styles.css`
- `backend/deployable/silver-refinement-agent/modules/silver_agents/profile_report.py`
- `backend/deployable/silver-refinement-agent/modules/silver_agents/router.py`
- `backend/deployable/silver-refinement-agent/tests/test_silver_agents.py`

## Siguiente paso de despliegue

Construir backend candidato, ejecutar smoke de catalogo/perfil/PDF, construir frontend contra ese candidato y validar en pantalla con una tabla distinta de `cat_producto` (por ejemplo `pagos_primas`). Solo despues promover ambos servicios.
