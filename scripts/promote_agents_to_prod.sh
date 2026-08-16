#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
BACKEND_SERVICE="silver-refinement-agent"
FRONTEND_SERVICE="business-rules-silver-ui"
BACKEND_IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/dataops/silver-refinement-agent:agents-8.2.0-2760098b-aefa-4b12-b645-6dad72428a3a"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
STAMP="$(date -u +%Y%m%d%H%M%S)"
GIT_SHA="$(git rev-parse --short HEAD)"
FRONTEND_TAG="agents-prod-${GIT_SHA}-${STAMP}"
FRONTEND_IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/dataops/business-rules-silver-ui:${FRONTEND_TAG}"

prepare_service_yaml() {
  local service_name="$1"
  local image_name="$2"
  local revision_name="$3"
  local output_path="$4"
  local source_path="/tmp/${service_name}-source-${STAMP}.yaml"

  gcloud run services describe "$service_name" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format=export > "$source_path"

  python - "$source_path" "$output_path" "$image_name" "$revision_name" <<'PY'
from pathlib import Path
import sys

source, target, image, revision = sys.argv[1:]
lines = Path(source).read_text().splitlines()
out = []
i = 0
in_template = False
in_template_metadata = False
image_replaced = False
revision_replaced = False

while i < len(lines):
    line = lines[i]

    if line == "status:":
        break

    if line == "  traffic:":
        i += 1
        while i < len(lines):
            candidate = lines[i]
            if candidate.startswith("    ") or candidate.startswith("  -"):
                i += 1
                continue
            break
        continue

    if line == "  template:":
        in_template = True
        in_template_metadata = False
    elif in_template and line == "    metadata:":
        in_template_metadata = True
    elif in_template_metadata and line.startswith("    ") and not line.startswith("      "):
        in_template_metadata = False

    if in_template_metadata and line.startswith("      name: "):
        line = f"      name: {revision}"
        revision_replaced = True

    if line.startswith("        image: "):
        line = f"        image: {image}"
        image_replaced = True

    out.append(line)
    i += 1

if not revision_replaced:
    try:
        metadata_index = out.index("    metadata:")
    except ValueError as exc:
        raise SystemExit("No se encontró spec.template.metadata") from exc
    out.insert(metadata_index + 1, f"      name: {revision}")
    revision_replaced = True
if not image_replaced:
    raise SystemExit("No se encontró la imagen del contenedor")

Path(target).write_text("\n".join(out) + "\n")
PY
}

echo "=== PROMOTE BACKEND ==="
BACKEND_REVISION="silver-refinement-agent-agents820-${STAMP}"
BACKEND_YAML="/tmp/silver-refinement-agent-prod-${STAMP}.yaml"
prepare_service_yaml "$BACKEND_SERVICE" "$BACKEND_IMAGE" "$BACKEND_REVISION" "$BACKEND_YAML"

gcloud run services replace "$BACKEND_YAML" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --quiet

gcloud run services update-traffic "$BACKEND_SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --to-revisions="${BACKEND_REVISION}=100" \
  --quiet

echo "=== VERIFY BACKEND ==="
gcloud run revisions describe "$BACKEND_REVISION" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="yaml(metadata.name,spec.containers[0].image,status.imageDigest)"

curl -fsS "$BACKEND_URL/health" | tee /tmp/silver-health.json | jq -e \
  '.status == "ok" and .version == "8.2.0"'

curl -fsS -D /tmp/silver-cors.headers -o /tmp/silver-cors.body \
  -X OPTIONS "$BACKEND_URL/silver-agents" \
  -H "Origin: $FRONTEND_URL" \
  -H "Access-Control-Request-Method: GET"

grep -qi '^access-control-allow-origin: \*' /tmp/silver-cors.headers

curl -fsS "$BACKEND_URL/silver-agents" | tee /tmp/silver-agents.json | jq -e \
  'map(.name) | sort == ["business-rule-validator","notebook-generator","orchestrator","quality-rule-advisor","table-profiler"]'

echo "=== BUILD FRONTEND FOR PROD BACKEND ==="
gcloud builds submit . \
  --project="$PROJECT_ID" \
  --config=cloudbuild.frontend-agents-prod.yaml \
  --substitutions="_IMAGE_TAG=${FRONTEND_TAG},_BACKEND_URL=${BACKEND_URL}"

echo "=== PROMOTE FRONTEND ==="
FRONTEND_REVISION="business-rules-silver-ui-agents-${STAMP}"
FRONTEND_YAML="/tmp/business-rules-silver-ui-prod-${STAMP}.yaml"
prepare_service_yaml "$FRONTEND_SERVICE" "$FRONTEND_IMAGE" "$FRONTEND_REVISION" "$FRONTEND_YAML"

gcloud run services replace "$FRONTEND_YAML" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --quiet

gcloud run services update-traffic "$FRONTEND_SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --to-revisions="${FRONTEND_REVISION}=100" \
  --quiet

echo "=== VERIFY FRONTEND ==="
gcloud run revisions describe "$FRONTEND_REVISION" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="yaml(metadata.name,spec.containers[0].image,status.imageDigest)"

INDEX_HTML="$(curl -fsS "$FRONTEND_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "${FRONTEND_URL}${ASSET_PATH}" > /tmp/business-rules-silver-prod.js

grep -Fq "$BACKEND_URL" /tmp/business-rules-silver-prod.js
if grep -Fq "silver-refinement-agent-merge-test" /tmp/business-rules-silver-prod.js; then
  echo "ERROR: el bundle productivo referencia el backend de prueba" >&2
  exit 1
fi

curl -fsSI "$FRONTEND_URL" | sed -n '1,20p'

echo "=== PRODUCTION PROMOTION CONFORME ==="
echo "BACKEND_REVISION=$BACKEND_REVISION"
echo "BACKEND_IMAGE=$BACKEND_IMAGE"
echo "FRONTEND_REVISION=$FRONTEND_REVISION"
echo "FRONTEND_IMAGE=$FRONTEND_IMAGE"
echo "FRONTEND_URL=$FRONTEND_URL"
echo "BACKEND_URL=$BACKEND_URL"
