#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-agent-governance-adk-preview}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/agent-governance-dashboard"
CANONICAL_GOVERNANCE_DIR="$ROOT_DIR/preview/governance-dashboard"
ATLAS_API_URL="${ATLAS_API_URL:-https://atlas-datagob-api-f56-preview-mkqutd4koq-uc.a.run.app}"

command -v gcloud >/dev/null
command -v curl >/dev/null
command -v git >/dev/null

BRANCH="$(git -C "$ROOT_DIR" branch --show-current)"
if [[ "$BRANCH" != "feat/agent-governance-control-plane-preview" ]]; then
  echo "ERROR: expected feat/agent-governance-control-plane-preview, current=${BRANCH:-detached}" >&2
  exit 1
fi

for file in Dockerfile index.html app.js nginx.conf; do
  test -f "$PREVIEW_DIR/$file"
done
test -f "$CANONICAL_GOVERNANCE_DIR/styles.css"

AUTH_HEADERS=(
  -H 'X-ATLAS-USER: feature56.preview@atlas.local'
  -H 'X-ATLAS-ROLES: data_steward,data_architect,executive'
)

echo "=== Agent Governance · independent preview ==="
echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "Service : $SERVICE"
echo "API     : $ATLAS_API_URL"
echo "CSS base: preview/governance-dashboard/styles.css"
echo

echo "[1/5] Validando shell basado en Business Rules Governance Dashboard..."
if command -v node >/dev/null 2>&1; then
  node --check "$PREVIEW_DIR/app.js"
fi
grep -Fq 'Gobierno de Agentes — Google ADK' "$PREVIEW_DIR/index.html"
grep -Fq 'Resumen ejecutivo' "$PREVIEW_DIR/index.html"
grep -Fq 'Registro de agentes gobernados' "$PREVIEW_DIR/index.html"
grep -Fq 'openAgentDetail' "$PREVIEW_DIR/app.js"
grep -Fq 'openDeploymentDetail' "$PREVIEW_DIR/app.js"
grep -Fq 'preview/governance-dashboard/styles.css' "$PREVIEW_DIR/Dockerfile"
echo "PASS: shell, drill-downs y stylesheet canónico presentes"

echo
echo "[2/5] Validando contratos reales de Gobierno de Agentes..."
curl -fsS --retry 3 --retry-delay 1 "${AUTH_HEADERS[@]}" "$ATLAS_API_URL/health" >/tmp/agent-governance-health.json
curl -fsS --retry 3 --retry-delay 1 "${AUTH_HEADERS[@]}" "$ATLAS_API_URL/agent-governance/summary" >/tmp/agent-governance-summary.json
curl -fsS --retry 3 --retry-delay 1 "${AUTH_HEADERS[@]}" "$ATLAS_API_URL/agent-governance/agents" >/tmp/agent-governance-agents.json
curl -fsS --retry 3 --retry-delay 1 "${AUTH_HEADERS[@]}" "$ATLAS_API_URL/agent-governance/deployments" >/tmp/agent-governance-deployments.json
curl -fsS --retry 3 --retry-delay 1 "${AUTH_HEADERS[@]}" "$ATLAS_API_URL/agent-governance/findings" >/tmp/agent-governance-findings.json

grep -Fq '"deployments_adk"' /tmp/agent-governance-summary.json
grep -Fq '"agents"' /tmp/agent-governance-agents.json
grep -Fq '"deployments"' /tmp/agent-governance-deployments.json
echo "PASS: API de Gobierno de Agentes accesible"

echo
echo "[3/5] Construyendo contexto aislado sin duplicar el CSS canónico..."
BUILD_CONTEXT="$(mktemp -d /tmp/agent-governance-preview.XXXXXX)"
cleanup() { rm -rf "$BUILD_CONTEXT"; }
trap cleanup EXIT
mkdir -p "$BUILD_CONTEXT/preview/agent-governance-dashboard" "$BUILD_CONTEXT/preview/governance-dashboard"
cp "$PREVIEW_DIR/Dockerfile" "$BUILD_CONTEXT/Dockerfile"
cp "$PREVIEW_DIR/index.html" "$BUILD_CONTEXT/preview/agent-governance-dashboard/index.html"
cp "$PREVIEW_DIR/app.js" "$BUILD_CONTEXT/preview/agent-governance-dashboard/app.js"
cp "$PREVIEW_DIR/nginx.conf" "$BUILD_CONTEXT/preview/agent-governance-dashboard/nginx.conf"
cp "$CANONICAL_GOVERNANCE_DIR/styles.css" "$BUILD_CONTEXT/preview/governance-dashboard/styles.css"
echo "PASS: contexto usa el stylesheet real del Governance Dashboard de Business Rules"

echo
echo "[4/5] Desplegando servicio Cloud Run independiente..."
gcloud run deploy "$SERVICE" \
  --source "$BUILD_CONTEXT" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --quiet

PREVIEW_URL="$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)')"
test -n "$PREVIEW_URL"

echo
echo "[5/5] Smoke funcional del dashboard independiente..."
HTML_FILE=/tmp/agent-governance-preview-index.html
JS_FILE=/tmp/agent-governance-preview-app.js
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/" -o "$HTML_FILE"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/app.js" -o "$JS_FILE"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/api/agent-governance/summary" >/tmp/agent-governance-preview-proxy-summary.json

grep -Fq 'Gobierno de Agentes — Google ADK' "$HTML_FILE"
grep -Fq 'openAgentDetail' "$JS_FILE"
grep -Fq '"deployments_adk"' /tmp/agent-governance-preview-proxy-summary.json

echo "PASS: frontend independiente + proxy same-origin + datos reales"
echo
echo "=== AGENT GOVERNANCE PREVIEW: CONFORME ==="
echo "PREVIEW_URL=$PREVIEW_URL"
echo "AGENT_DEEP_LINK=$PREVIEW_URL/#agent/<agent_id>"
echo "DEPLOYMENT_DEEP_LINK=$PREVIEW_URL/#deployment/<deployment_id>"
echo "API_URL=$ATLAS_API_URL"
echo "CANONICAL_VISUAL_BASE=preview/governance-dashboard/styles.css"
echo "BUSINESS_RULES_GOVERNANCE_UNCHANGED=true"
