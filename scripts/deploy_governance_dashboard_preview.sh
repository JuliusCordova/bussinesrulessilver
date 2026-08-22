#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-business-rules-silver-governance-preview}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/governance-dashboard"
EXPECTED_BACKEND_URL="${SILVER_API_URL:-https://silver-refinement-agent-mkqutd4koq-uc.a.run.app}"
FINOPS_API_URL="${FINOPS_API_URL:-https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app}"

command -v gcloud >/dev/null
command -v curl >/dev/null

for file in Dockerfile index.html app.js styles.css finops.js finops.css theme-red.css spa.css product-polish.css router.js finops-polish.js quality.js quality.css; do
  test -f "$PREVIEW_DIR/$file"
done

echo "=== Gobierno DataOps interactive preview ==="
echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "Service : $SERVICE"
echo "Backend : $EXPECTED_BACKEND_URL"
echo "FinOps  : $FINOPS_API_URL"
echo

echo "[1/6] Validando frontend preview..."
if command -v node >/dev/null 2>&1; then
  node --check "$PREVIEW_DIR/app.js"
  node --check "$PREVIEW_DIR/finops.js"
  node --check "$PREVIEW_DIR/router.js"
  node --check "$PREVIEW_DIR/finops-polish.js"
  node --check "$PREVIEW_DIR/quality.js"
fi
bash "$ROOT_DIR/scripts/validate_governance_preview_spa.sh"
grep -Fq 'detailDrawer' "$PREVIEW_DIR/index.html"
grep -Fq 'id="finops"' "$PREVIEW_DIR/index.html"
grep -Fq 'finopsTokenTrend' "$PREVIEW_DIR/index.html"
grep -Fq 'finopsServiceCosts' "$PREVIEW_DIR/index.html"
grep -Fq 'FACTURADO' "$PREVIEW_DIR/index.html"
grep -Fq 'ATRIBUIDO' "$PREVIEW_DIR/index.html"
grep -Fq 'openRunDetail' "$PREVIEW_DIR/app.js"
grep -Fq 'openAgentDetail' "$PREVIEW_DIR/app.js"
for path in summary daily agents runs services; do
  grep -Fq "/agentops/finops/$path" "$PREVIEW_DIR/finops.js"
done
grep -Fq '/agentops/finops/product-attribution' "$PREVIEW_DIR/finops-polish.js"
echo "PASS: shell interactivo, navegación SPA y FinOps Billing-aware presentes"

echo
echo "[2/6] Validando backend canónico..."
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/health" >/tmp/governance-preview-backend-health.json
grep -Fq '"status"' /tmp/governance-preview-backend-health.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/governance/summary" >/tmp/governance-preview-summary.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/governance/runs?limit=1" >/tmp/governance-preview-runs.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/health" >/tmp/governance-preview-health.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/silver-agents" >/tmp/governance-preview-agents.json
echo "PASS: backend y contratos AgentOps accesibles"

echo
echo "[3/6] Validando FinOps real del candidato..."
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/summary?days=30" >/tmp/governance-preview-finops-summary.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/daily?days=30" >/tmp/governance-preview-finops-daily.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/agents?days=30" >/tmp/governance-preview-finops-agents.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/runs?days=30&limit=20" >/tmp/governance-preview-finops-runs.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/services?days=30" >/tmp/governance-preview-finops-services.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/product-attribution?days=30" >/tmp/governance-preview-finops-product.json
python3 - <<'PY'
import json
from pathlib import Path
s=json.loads(Path('/tmp/governance-preview-finops-summary.json').read_text())
d=json.loads(Path('/tmp/governance-preview-finops-daily.json').read_text())
a=json.loads(Path('/tmp/governance-preview-finops-agents.json').read_text())
r=json.loads(Path('/tmp/governance-preview-finops-runs.json').read_text())
v=json.loads(Path('/tmp/governance-preview-finops-services.json').read_text())
p=json.loads(Path('/tmp/governance-preview-finops-product.json').read_text())
assert int(s.get('llm_calls') or 0)>0, s
assert int(s.get('total_tokens') or 0)>0, s
assert isinstance(d.get('series'),list) and d['series'], d
assert isinstance(a.get('agents'),list) and a['agents'], a
assert a.get('cost_usd') is None, a
assert isinstance(r.get('runs'),list) and r['runs'], r
assert r.get('cost_usd') is None, r
assert p.get('product')=='BUSINESS_RULES_SILVER', p
if p.get('temporal_overlap') is False:
    assert p.get('product_cost_usd') is None, p
    assert p.get('attributed_ai_cost_usd') is None, p
    assert p.get('status')=='WAITING_TEMPORAL_OVERLAP', p
billing_source=s.get('billing_source_available') is True
billing_cost=s.get('billing_cost_available') is True
assert v.get('billing_source_available') is billing_source,(s,v)
assert v.get('billing_cost_available') is billing_cost,(s,v)
if billing_cost:
    assert s.get('cost_semantics')=='FACTURADO',s
    assert s.get('cost_usd') is not None,s
    print(f"PASS: FinOps real + Billing real con cobertura ({s.get('billing_currency')} / USD {s.get('cost_usd')})")
elif billing_source:
    assert s.get('cost_usd') is None,s
    assert s.get('cost_source')=='CLOUD_BILLING_EXPORT_NOT_YET_COVERING_PERIOD',s
    print(f"PASS: FinOps real; Billing materializado en backfill (último uso: {s.get('last_usage_at')})")
else:
    assert s.get('cost_usd') is None,s
    print('PASS: FinOps real; Billing pendiente, sin USD sintéticos')
PY

echo
echo "[4/6] Desplegando preview aislado en Cloud Run..."
gcloud run deploy "$SERVICE" \
  --source "$PREVIEW_DIR" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --quiet

PREVIEW_URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
test -n "$PREVIEW_URL"

echo
echo "[5/6] Smoke test del frontend desplegado..."
PREVIEW_HTML=/tmp/governance-preview-index.html
PREVIEW_JS=/tmp/governance-preview-app.js
PREVIEW_FINOPS_JS=/tmp/governance-preview-finops.js
PREVIEW_ROUTER_JS=/tmp/governance-preview-router.js
PREVIEW_FINOPS_POLISH_JS=/tmp/governance-preview-finops-polish.js
PREVIEW_SPA_CSS=/tmp/governance-preview-spa.css
PREVIEW_PRODUCT_POLISH_CSS=/tmp/governance-preview-product-polish.css
PREVIEW_QUALITY_JS=/tmp/governance-preview-quality.js
PREVIEW_QUALITY_CSS=/tmp/governance-preview-quality.css
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/" -o "$PREVIEW_HTML"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/app.js" -o "$PREVIEW_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/finops.js" -o "$PREVIEW_FINOPS_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/router.js" -o "$PREVIEW_ROUTER_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/finops-polish.js" -o "$PREVIEW_FINOPS_POLISH_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/spa.css" -o "$PREVIEW_SPA_CSS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/product-polish.css" -o "$PREVIEW_PRODUCT_POLISH_CSS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/quality.js" -o "$PREVIEW_QUALITY_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/quality.css" -o "$PREVIEW_QUALITY_CSS"

grep -Fq 'Gobierno DataOps — Business Rules Silver' "$PREVIEW_HTML"
grep -Fq 'data-view-target="overview"' "$PREVIEW_HTML"
grep -Fq 'data-view-target="finops"' "$PREVIEW_HTML"
grep -Fq 'data-view-target="quality"' "$PREVIEW_HTML"
grep -Fq './quality.css' "$PREVIEW_HTML"
grep -Fq './product-polish.css' "$PREVIEW_HTML"
grep -Fq '/agentops/governance/summary' "$PREVIEW_JS"
grep -Fq '/agentops/finops/services' "$PREVIEW_FINOPS_JS"
grep -Fq 'function show' "$PREVIEW_ROUTER_JS"
grep -Fq '#view/' "$PREVIEW_ROUTER_JS"
grep -Fq '/agentops/finops/product-attribution' "$PREVIEW_FINOPS_POLISH_JS"
grep -Fq 'governance-view[hidden]' "$PREVIEW_SPA_CSS"
grep -Fq 'finops-product-panel' "$PREVIEW_PRODUCT_POLISH_CSS"
grep -Fq '/silver-workflows?limit=50' "$PREVIEW_QUALITY_JS"
grep -Fq 'BLOCK_LOAD' "$PREVIEW_QUALITY_JS"
grep -Fq '.quality-section' "$PREVIEW_QUALITY_CSS"
grep -Fq 'No disponible' "$PREVIEW_FINOPS_POLISH_JS"
echo "PASS: preview desplegado contiene SPA, pulida ejecutiva y FinOps real"

echo
echo "[6/6] Preview listo"
echo "========================================================"
echo "PREVIEW_URL=$PREVIEW_URL"
echo "OVERVIEW_URL=$PREVIEW_URL/#view/overview"
echo "FINOPS_URL=$PREVIEW_URL/#view/finops"
echo "QUALITY_URL=$PREVIEW_URL/#view/quality"
echo "DEEP_LINK_FORMAT=$PREVIEW_URL/#run/<run_id>"
echo "BACKEND_URL=$EXPECTED_BACKEND_URL"
echo "FINOPS_API_URL=$FINOPS_API_URL"
echo "========================================================"
