from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:140]!r}")
    file.write_text(text.replace(old, new, 1))

API = "src/api.ts"
RESUME = "src/workflowResume.ts"

replace(
    API,
    "import type { CatalogField, GeneratedArtifact, WorkflowState } from './types';\n",
    "import type { CatalogField, GeneratedArtifact, GovernedQualityRule, WorkflowState } from './types';\n",
)

replace(
    API,
    "  approved_quality_rules?: Array<Record<string, unknown>>;\n",
    "  approved_quality_rules?: GovernedQualityRule[];\n",
)

replace(
    RESUME,
    "import type { WorkflowState } from './types';\n",
    "import type { GovernedQualityRule, WorkflowState } from './types';\n",
)

replace(
    RESUME,
    "    approvedQualityRules: workflow.quality_rules ?? [],\n",
    "    approvedQualityRules: (workflow.quality_rules ?? []) as GovernedQualityRule[],\n",
)

print("PASS: Quality Rule Designer 2A typing recovery aplicado.")
print("API y rehidratación comparten GovernedQualityRule sin widening a Record<string, unknown>.")
