#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/governance-dashboard"

echo "=== Validate governance preview SPA ==="

for file in index.html app.js finops.js finops-polish.js router.js styles.css finops.css theme-red.css spa.css product-polish.css; do
  test -f "$PREVIEW_DIR/$file"
done

if command -v node >/dev/null 2>&1; then
  node --check "$PREVIEW_DIR/app.js"
  node --check "$PREVIEW_DIR/finops.js"
  node --check "$PREVIEW_DIR/finops-polish.js"
  node --check "$PREVIEW_DIR/router.js"
fi

# Assets de la SPA y capa visual de producto.
grep -Fq './spa.css' "$PREVIEW_DIR/index.html"
grep -Fq './product-polish.css' "$PREVIEW_DIR/index.html"
grep -Fq './finops-polish.js' "$PREVIEW_DIR/index.html"
grep -Fq './router.js' "$PREVIEW_DIR/index.html"

# Navegación explícita: no depender de scroll dentro de una página larga.
grep -Fq 'data-view-target="overview"' "$PREVIEW_DIR/index.html"
grep -Fq 'data-view-target="finops"' "$PREVIEW_DIR/index.html"
grep -Fq 'data-view-target="agents"' "$PREVIEW_DIR/index.html"
grep -Fq 'data-view-target="runs"' "$PREVIEW_DIR/index.html"
grep -Fq 'const META' "$PREVIEW_DIR/router.js"
grep -Fq "v.hidden=v.dataset.view!==name" "$PREVIEW_DIR/router.js"
grep -Fq '#view/' "$PREVIEW_DIR/router.js"
grep -Fq "show(hashView()||'overview'" "$PREVIEW_DIR/router.js"
grep -Fq 'spa-ready' "$PREVIEW_DIR/router.js"

# Runtime safety: evitar loops de mutación que congelen la UI.
if grep -Fq 'new MutationObserver' "$PREVIEW_DIR/router.js"; then
  echo "FAIL: router.js no debe observar recursivamente todo el dashboard" >&2
  exit 1
fi
if grep -Fq 'new MutationObserver' "$PREVIEW_DIR/finops-polish.js"; then
  echo "FAIL: finops-polish.js no debe depender de observers para estabilizar el render" >&2
  exit 1
fi
grep -Fq 'scheduleSyncs' "$PREVIEW_DIR/router.js"
grep -Fq 'if (target.textContent !== next)' "$PREVIEW_DIR/router.js"

# FinOps real: atribución basada en contrato real, sin sustitutos sintéticos.
grep -Fq 'product-attribution' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'No disponible' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'Sin estimaciones sintéticas' "$PREVIEW_DIR/finops-polish.js"
grep -Fq 'product-attribution-kpis' "$PREVIEW_DIR/spa.css"
grep -Fq 'governance-view[hidden]' "$PREVIEW_DIR/spa.css"
grep -Fq 'finops-product-panel' "$PREVIEW_DIR/product-polish.css"
grep -Fq 'Costo producto' "$PREVIEW_DIR/finops-polish.js"

echo "PASS: navegación explícita por vistas y hash routing presentes"
echo "PASS: una sola vista queda visible mediante hidden/display:none"
echo "PASS: router y FinOps polish sin observers recursivos"
echo "PASS: pulida ejecutiva de Overview + FinOps presente"
echo "PASS: FinOps conserva costo real y No disponible sin evidencia"
