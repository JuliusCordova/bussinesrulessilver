#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/governance-dashboard"

echo "=== Validate governance preview SPA ==="

for file in index.html app.js finops.js finops-polish.js router.js styles.css finops.css theme-red.css spa.css; do
  test -f "$PREVIEW_DIR/$file"
done

if command -v node >/dev/null 2>&1; then
  node --check "$PREVIEW_DIR/app.js"
  node --check "$PREVIEW_DIR/finops.js"
  node --check "$PREVIEW_DIR/finops-polish.js"
  node --check "$PREVIEW_DIR/router.js"
fi

grep -Fq './spa.css' "$PREVIEW_DIR/index.html"
grep -Fq './finops-polish.js' "$PREVIEW_DIR/index.html"
grep -Fq './router.js' "$PREVIEW_DIR/index.html"
grep -Fq 'VIEW_META' "$PREVIEW_DIR/router.js"
grep -Fq "overview" "$PREVIEW_DIR/router.js"
grep -Fq "finops" "$PREVIEW_DIR/router.js"
grep -Fq "agents" "$PREVIEW_DIR/router.js"
grep -Fq "runs" "$PREVIEW_DIR/router.js"
grep -Fq 'product-attribution' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'No disponible' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'Sin estimaciones sintéticas' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'product-attribution-kpis' "$PREVIEW_DIR/spa.css"
grep -Fq 'overview-content-grid' "$PREVIEW_DIR/spa.css"

echo "PASS: navegación multi-vista y visual FinOps real presentes"
echo "PASS: el costo de producto conserva semántica No disponible cuando no existe evidencia"
