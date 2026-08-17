#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
BACKEND_SERVICE="silver-refinement-agent"
FRONTEND_SERVICE="business-rules-silver-ui"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
EXPECTED_BACKEND_DIGEST="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent@sha256:cafdc4322ca6e38c43560d5350ab32872f720b4ce111e1c88ea5318d06d8cb26"
FRONTEND_IMAGE="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui:agents-prod-5c718b1-20260817021109"
STAMP="$(date -u +%Y%m%d%H%M%S)"
FRONTEND_REVISION="business-rules-silver-ui-governance-${STAMP}"
SOURCE_YAML="/tmp/business-rules-silver-ui-source-${STAMP}.yaml"
TARGET_YAML="/tmp/business-rules-silver-ui-governance-${STAMP}.yaml"

echo "=== VERIFY PROMOTED BACKEND ==="
BACKEND_REVISION="$(gcloud run services describe "$BACKEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.traffic[0].revisionName)')"
BACKEND_DIGEST="$(gcloud run revisions describe "$BACKEND_REVISION" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.imageDigest)')"
test "$BACKEND_DIGEST" = "$EXPECTED_BACKEND_DIGEST"
curl -fsS "$BACKEND_URL/health" | jq -e '.status == "ok" and .version == "8.2.0"'
curl -fsS "$BACKEND_URL/agentops/governance/summary" | jq -e 'has("total_runs")'

echo "=== PREPARE FRONTEND REVISION ==="
gcloud run services describe "$FRONTEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format=export > "$SOURCE_YAML"

python - "$SOURCE_YAML" "$TARGET_YAML" "$FRONTEND_IMAGE" "$FRONTEND_REVISION" <<'PY'
from pathlib import Path
import sys

source, target, image, revision = sys.argv[1:]
lines = Path(source).read_text().splitlines()
out = []
in_template = False
in_template_metadata = False
image_replaced = False
revision_replaced = False
i = 0

while i < len(lines):
    line = lines[i]
    if line == "status:":
        break
    if line == "  traffic:":
        i += 1
        while i < len(lines) and (
            lines[i].startswith("    ") or lines[i].startswith("  -")
        ):
            i += 1
        continue
    if line == "  template:":
        in_template = True
        in_template_metadata = False
    elif in_template and line == "    metadata:":
        in_template_metadata = True
    elif in_template_metadata and line.startswith("    ") and not line.startswith("      "):
        in_template_metadata = False
    if in_template_metadata and line.lstrip().startswith("name: "):
        indent = line[: len(line) - len(line.lstrip())]
        line = f"{indent}name: {revision}"
        revision_replaced = True
    if in_template and line.lstrip().startswith("image: "):
        indent = line[: len(line) - len(line.lstrip())]
        line = f"{indent}image: {image}"
        image_replaced = True
    out.append(line)
    i += 1

if not revision_replaced:
    metadata_index = out.index("    metadata:")
    out.insert(metadata_index + 1, f"      name: {revision}")
if not image_replaced:
    raise SystemExit("No se encontró spec.template.spec.containers[].image")
Path(target).write_text("\n".join(out) + "\n")
PY

grep -nE 'name: business-rules-silver-ui-governance|image: .*agents-prod-5c718b1' "$TARGET_YAML"

echo "=== DEPLOY FRONTEND ONLY ==="
gcloud run services replace "$TARGET_YAML" \
  --project="$PROJECT_ID" --region="$REGION" --quiet
gcloud run services update-traffic "$FRONTEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --to-revisions="${FRONTEND_REVISION}=100" --quiet

echo "=== VERIFY FRONTEND ==="
gcloud run revisions describe "$FRONTEND_REVISION" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='yaml(metadata.name,spec.containers[0].image,status.imageDigest)'

INDEX_HTML="$(curl -fsS "$FRONTEND_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "${FRONTEND_URL}${ASSET_PATH}" > /tmp/business-rules-silver-governance-prod.js
grep -Fq "$BACKEND_URL" /tmp/business-rules-silver-governance-prod.js
! grep -Fq "silver-refinement-agent-merge-test" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Ejecutar Quality Review" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Gobierno agéntico persistente" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Persistencia BigQuery" /tmp/business-rules-silver-governance-prod.js
curl -fsSI "$FRONTEND_URL" | sed -n '1,20p'

echo "=== GOVERNANCE RELEASE PRODUCTION CONFORME ==="
echo "BACKEND_REVISION=$BACKEND_REVISION"
echo "BACKEND_DIGEST=$BACKEND_DIGEST"
echo "FRONTEND_REVISION=$FRONTEND_REVISION"
echo "FRONTEND_IMAGE=$FRONTEND_IMAGE"
echo "FRONTEND_URL=$FRONTEND_URL"
