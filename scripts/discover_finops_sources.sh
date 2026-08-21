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

printf '[1/7] Billing association...\n'
if gcloud billing projects describe "$PROJECT_ID" --format=json >"$OUT/billing-project.json" 2>"$OUT/billing-project.err"; then
  BILLING_ENABLED="$(python3 - "$OUT/billing-project.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1]))
print(str(bool(p.get('billingEnabled'))).lower())
PY
)"
  echo "PASS: asociación de billing consultada (billingEnabled=$BILLING_ENABLED)"
else
  echo 'WARN: no se pudo consultar asociación de billing; revisar billing-project.err'
fi

printf '\n[2/7] BigQuery datasets del proyecto...\n'
bq ls --project_id="$PROJECT_ID" --format=prettyjson >"$OUT/bq-datasets.json"
echo 'PASS: datasets listados'

printf '\n[3/7] Cloud Billing Export real...\n'
python3 - "$PROJECT_ID" "$OUT" <<'PY'
import json, pathlib, subprocess, sys
project, out = sys.argv[1], pathlib.Path(sys.argv[2])
datasets = json.loads((out / 'bq-datasets.json').read_text() or '[]')
billing = []
telemetry = []
all_matches = []
for ds in datasets:
    dataset_id = ds.get('datasetReference', {}).get('datasetId') or ds.get('id', '').split(':')[-1]
    if not dataset_id:
        continue
    proc = subprocess.run(['bq','ls','--project_id='+project,'--format=prettyjson',dataset_id], capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        continue
    try:
        tables = json.loads(proc.stdout)
    except json.JSONDecodeError:
        continue
    for table in tables:
        table_id = table.get('tableReference', {}).get('tableId') or table.get('id', '').split('.')[-1]
        if not table_id:
            continue
        lower = table_id.lower()
        entry = {'dataset': dataset_id, 'table': table_id}
        # Official Cloud Billing BigQuery export table prefixes.
        if lower.startswith(('gcp_billing_export_v1_', 'gcp_billing_export_resource_v1_', 'cloud_pricing_export')):
            billing.append(entry)
        elif any(k in f'{dataset_id}.{table_id}'.lower() for k in ('billing','cost','usage','llm','token')):
            telemetry.append(entry)
        if any(k in f'{dataset_id}.{table_id}'.lower() for k in ('billing','cost','usage','llm','token')):
            all_matches.append(entry)
(out / 'cloud-billing-export-tables.json').write_text(json.dumps(billing, indent=2))
(out / 'operational-usage-candidates.json').write_text(json.dumps(telemetry, indent=2))
(out / 'all-finops-candidates.json').write_text(json.dumps(all_matches, indent=2))
print('Cloud Billing Export tables:')
print(json.dumps(billing, indent=2))
print('Operational / AI usage candidates:')
print(json.dumps(telemetry, indent=2))
if billing:
    print('RESULT: BILLING_EXPORT_FOUND')
else:
    print('RESULT: BILLING_EXPORT_NOT_FOUND')
PY

printf '\n[4/7] AgentOps usage views...\n'
for VIEW in vw_llm_usage_summary vw_tool_usage; do
  if bq show --project_id="$PROJECT_ID" --format=prettyjson "agentops.$VIEW" >"$OUT/${VIEW}.json" 2>"$OUT/${VIEW}.err"; then
    echo "FOUND: agentops.$VIEW"
    bq show --project_id="$PROJECT_ID" --schema --format=prettyjson "agentops.$VIEW" >"$OUT/${VIEW}-schema.json" || true
  else
    echo "NOT FOUND: agentops.$VIEW"
  fi
done

printf '\n[5/7] Servicios Cloud Run relacionados...\n'
gcloud run services list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='table(metadata.name,status.url)' >"$OUT/cloud-run-services.txt"
grep -Ei 'silver|business-rules|governance' "$OUT/cloud-run-services.txt" || true

printf '\n[6/7] Configuración del backend Silver...\n'
if gcloud run services describe silver-refinement-agent \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format=json >"$OUT/silver-refinement-agent.json" 2>"$OUT/silver-refinement-agent.err"; then
  echo 'PASS: configuración de silver-refinement-agent capturada'
else
  echo 'WARN: no se pudo describir silver-refinement-agent'
fi

printf '\n[7/7] APIs relevantes habilitadas...\n'
gcloud services list --enabled --project="$PROJECT_ID" \
  --filter='config.name:(cloudbilling.googleapis.com OR bigquery.googleapis.com OR aiplatform.googleapis.com OR run.googleapis.com OR monitoring.googleapis.com)' \
  --format='value(config.name)' >"$OUT/enabled-finops-apis.txt"
cat "$OUT/enabled-finops-apis.txt"

printf '\n=== DISCOVERY COMPLETADO ===\n'
printf 'EVIDENCE_DIR=%s\n' "$OUT"
printf '\nCriterio de avance:\n'
printf '1) Solo cloud-billing-export-tables.json habilita KPIs de costo facturado.\n'
printf '2) operational-usage-candidates.json es telemetría y NO equivale a facturación.\n'
printf '3) Si Billing Export no existe, el dashboard debe mostrar costo facturado como no disponible.\n'
