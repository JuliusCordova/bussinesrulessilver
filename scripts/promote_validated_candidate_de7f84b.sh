#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
VALIDATED_COMMIT="de7f84b"
VALIDATED_BACKEND_TAG="agents-8.2.0-a21715fb-2141-4cc5-84a6-0d2eb8779a78"
BACKEND_REPOSITORY="us-central1-docker.pkg.dev/$PROJECT_ID/dataops/silver-refinement-agent"
VALIDATED_BACKEND_IMAGE="$BACKEND_REPOSITORY:$VALIDATED_BACKEND_TAG"
BACKEND_PROD="silver-refinement-agent"
FRONTEND_PROD="business-rules-silver-ui"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
STAMP="$(date -u +%Y%m%d%H%M%S)"
WORKTREE="/tmp/bussinesrulessilver-validated-$STAMP"

cleanup() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

prepare_yaml() {
  service="$1"
  image="$2"
  revision="$3"
  target="$4"
  source="/tmp/$service-source-$STAMP.yaml"

  gcloud run services describe "$service"     --project="$PROJECT_ID" --region="$REGION" --format=export > "$source"

  python - "$source" "$target" "$image" "$revision" <<'PY'
from pathlib import Path
import sys

source, target, image, revision = sys.argv[1:]
lines = Path(source).read_text().splitlines()
out = []
i = 0
in_template = False
in_metadata = False
image_done = False
revision_done = False

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
        in_metadata = False
    elif in_template and line == "    metadata:":
        in_metadata = True
    elif in_metadata and line.startswith("    ") and not line.startswith("      "):
        in_metadata = False
    if in_metadata and line.startswith("      name: "):
        line = "      name: " + revision
        revision_done = True
    if line.startswith("        image: "):
        line = "        image: " + image
        image_done = True
    out.append(line)
    i += 1

if not revision_done:
    index = out.index("    metadata:")
    out.insert(index + 1, "      name: " + revision)
if not image_done:
    raise SystemExit("No se encontró imagen en YAML")
Path(target).write_text("\n".join(out) + "\n")
PY
}

echo "=== VALIDATED CUT ==="
git cat-file -e "$VALIDATED_COMMIT^{commit}"
git diff --quiet
git diff --cached --quiet

VALIDATED_DIGEST="$(gcloud artifacts docker images describe "$VALIDATED_BACKEND_IMAGE"   --project="$PROJECT_ID"   --format='value(image_summary.digest)')"
test -n "$VALIDATED_DIGEST"
VALIDATED_BACKEND_DIGEST="$BACKEND_REPOSITORY@$VALIDATED_DIGEST"

echo "VALIDATED_COMMIT=$VALIDATED_COMMIT"
echo "VALIDATED_BACKEND_IMAGE=$VALIDATED_BACKEND_IMAGE"
echo "VALIDATED_BACKEND_DIGEST=$VALIDATED_BACKEND_DIGEST"

gcloud run services describe "$BACKEND_PROD"   --project="$PROJECT_ID" --region="$REGION"   --format='yaml(status.latestReadyRevisionName,status.traffic)'   > "/tmp/backend-prod-before-$STAMP.yaml"
gcloud run services describe "$FRONTEND_PROD"   --project="$PROJECT_ID" --region="$REGION"   --format='yaml(status.latestReadyRevisionName,status.traffic)'   > "/tmp/frontend-prod-before-$STAMP.yaml"

echo "=== PROMOTE EXACT BACKEND CANDIDATE ==="
BACKEND_REVISION="silver-refinement-agent-validated-$STAMP"
BACKEND_YAML="/tmp/backend-validated-$STAMP.yaml"
prepare_yaml "$BACKEND_PROD" "$VALIDATED_BACKEND_DIGEST" "$BACKEND_REVISION" "$BACKEND_YAML"
gcloud run services replace "$BACKEND_YAML"   --project="$PROJECT_ID" --region="$REGION" --quiet
gcloud run services update-traffic "$BACKEND_PROD"   --project="$PROJECT_ID" --region="$REGION"   --to-revisions="$BACKEND_REVISION=100" --quiet

PROD_DIGEST="$(gcloud run revisions describe "$BACKEND_REVISION"   --project="$PROJECT_ID" --region="$REGION"   --format='value(status.imageDigest)')"
test "$PROD_DIGEST" = "$VALIDATED_BACKEND_DIGEST"
curl -fsS "$BACKEND_URL/health" | jq -e '.status == "ok" and .version == "8.2.0"'
curl -fsS "$BACKEND_URL/silver-agents" | jq -e   'map(.name) | sort == ["business-rule-validator","mapping-advisor","notebook-generator","orchestrator","quality-rule-advisor","table-profiler"]'

echo "=== BUILD FRONTEND FROM VALIDATED COMMIT ==="
git worktree add --detach "$WORKTREE" "$VALIDATED_COMMIT"
FRONTEND_TAG="validated-$VALIDATED_COMMIT-$STAMP"
FRONTEND_IMAGE="us-central1-docker.pkg.dev/$PROJECT_ID/dataops/business-rules-silver-ui:$FRONTEND_TAG"
gcloud builds submit "$WORKTREE"   --project="$PROJECT_ID"   --config="$WORKTREE/cloudbuild.frontend-agents-prod.yaml"   --substitutions="_IMAGE_TAG=$FRONTEND_TAG,_BACKEND_URL=$BACKEND_URL"

echo "=== PROMOTE VALIDATED FRONTEND ==="
FRONTEND_REVISION="business-rules-silver-ui-validated-$STAMP"
FRONTEND_YAML="/tmp/frontend-validated-$STAMP.yaml"
prepare_yaml "$FRONTEND_PROD" "$FRONTEND_IMAGE" "$FRONTEND_REVISION" "$FRONTEND_YAML"
gcloud run services replace "$FRONTEND_YAML"   --project="$PROJECT_ID" --region="$REGION" --quiet
gcloud run services update-traffic "$FRONTEND_PROD"   --project="$PROJECT_ID" --region="$REGION"   --to-revisions="$FRONTEND_REVISION=100" --quiet

echo "=== VERIFY PRODUCTION ==="
curl -fsSI "$FRONTEND_URL" | sed -n '1,20p'
INDEX_HTML="$(curl -fsS "$FRONTEND_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "$FRONTEND_URL$ASSET_PATH" > "/tmp/frontend-validated-$STAMP.js"
grep -Fq "$BACKEND_URL" "/tmp/frontend-validated-$STAMP.js"
! grep -Fq "silver-refinement-agent-merge-test" "/tmp/frontend-validated-$STAMP.js"

echo "=== VALIDATED CANDIDATE PROMOTED ==="
echo "BACKEND_REVISION=$BACKEND_REVISION"
echo "BACKEND_DIGEST=$PROD_DIGEST"
echo "FRONTEND_REVISION=$FRONTEND_REVISION"
echo "FRONTEND_IMAGE=$FRONTEND_IMAGE"
echo "FRONTEND_URL=$FRONTEND_URL"
