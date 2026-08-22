from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1))


API = "src/api.ts"
APP = "src/App.tsx"

replace(
    API,
    """  quality_rules?: Array<Record<string, unknown>>;\n  quality_rules_version?: number | null;\n""",
    """  quality_rules?: GovernedQualityRule[];\n  quality_rules_version?: number | null;\n""",
)

replace(
    APP,
    """                  approvedQualityRules: reviewed.quality_rules as GovernedQualityRule[],\n""",
    """                  approvedQualityRules: reviewed.quality_rules ?? [],\n""",
)

print("PASS: Runtime Quality Gates frontend typing recovery aplicado.")
print("SilverWorkflowRecord.quality_rules usa GovernedQualityRule[] y App elimina el cast inseguro.")
