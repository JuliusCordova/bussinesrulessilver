#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
OUTPUT_DIR="${OUTPUT_DIR:-docs/evidence/finops-discovery}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUTPUT_DIR/$STAMP"
mkdir -p "$OUT"

command -v gcloud >/dev/null
command -v bq >/dev/null

printf '=== FINOPS REAL SOURCE DISCOVERY ===\n'
printf 'Project: %s\n' "$PROJECT_ID"
printf 'Region : %s\n' "$REGION"
printf 'Output : %s\n\n' "$OUT"

printf '[1/6] Billing association...\n'
if gcloud billing projects describe "$PROJECT_ID" --format=json >"$OUT/billing-project.json" 2>"$OUT/billing-project.err"; then
  echo 'PASS: asociación de billing consultada'
else
  echo 'WARN: no se pudo consultar asociación de billing; revisar billing-project.err'
fi

printf '\n[2/6] BigQuery datasets del proyecto...\n'
bq ls --project_id="$PROJECT_ID" --format=prettyjson >"$OUT/bq-datasets.json"
echo 'PASS: datasets listados'

printf '\n[3/6] Tablas candidatas de Billing Export...\n'
python3 - "$PROJECT_ID" "$OUT" <<'PY'
import json, pathlib, subprocess, sys
project, out = sys.argv[1], pathlib.Path(sys.argv[2])
datasets = json.loads((out / 'bq-datasets.json').read_text() or '[]')
report = []
for ds in datasets:
    dataset_id = ds.get('datasetReference', {}).get('datasetId') or ds.get('id', '').split(':')[-1]
    if not dataset_id:
        continue
    proc = subprocess.run(['bq','ls','--project_id='+project,'--format=prettyjson',dataset_id], capture_output=True, text=True)
    tables = []
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            tables = json.loads(proc.stdout)
        except json.JSONDecodeError:
            tables = []
    for table in tables:
        table_id = table.get('tableReference', {}).get('tableId') or table.get('id', '').split('.')[-1]
        text = f'{dataset_id}.{table_id}'.lower()
        if any(k in text for k in ('gcp_billing_export','billing','cost','usage')):
            report.append({'dataset': dataset_id, 'table': table_id})
(out / 'billing-export-candidates.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
PY

printf '\n[4/6] Servicios Cloud Run relacionados...\n'
gcloud run services list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='table(metadata.name,status.url)' >"$OUT/cloud-run-services.txt"
grep -Ei 'silver|business-rules|governance' "$OUT/cloud-run-services.txt" || true

printf '\n[5/6] Configuración del backend Silver...\n'
if gcloud run services describe silver-refinement-agent \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format=json >"$OUT/silver-refinement-agent.json" 2>"$OUT/silver-refinement-agent.err"; then
  echo 'PASS: configuración de silver-refinement-agent capturada'
else
  echo 'WARN: no se pudo describir silver-refinement-agent'
fi

printf '\n[6/6] APIs relevantes habilitadas...\n'
gcloud services list --enabled --project="$PROJECT_ID" \
  --filter='config.name:(cloudbilling.googleapis.com OR bigquery.googleapis.com OR aiplatform.googleapis.com OR run.googleapis.com OR monitoring.googleapis.com)' \
  --format='value(config.name)' >"$OUT/enabled-finops-apis.txt"
cat "$OUT/enabled-finops-apis.txt"

printf '\n=== DISCOVERY COMPLETADO ===\n'
printf 'EVIDENCE_DIR=%s\n' "$OUT"
printf '\nSiguiente decisión:\n'
printf '1) Confirmar si billing-export-candidates.json contiene una tabla real de Cloud Billing Export.\n'
printf '2) No crear costos ni endpoints FinOps hasta validar la fuente.\n'
