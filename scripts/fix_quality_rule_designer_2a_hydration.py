from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/workflowResume.ts"
text = PATH.read_text()

old_import = "import type { CatalogField, MappingRule, StepId, WorkflowState } from './types';\n"
new_import = "import type { CatalogField, GovernedQualityRule, MappingRule, QualityDimension, QualityRuntimeAction, StepId, WorkflowState } from './types';\n"
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif new_import not in text:
    raise SystemExit("No se encontró el import esperado de workflowResume.ts")

anchor = "function inferKeys(workflow: SilverWorkflowRecord): string[] {\n"
helper = '''function governedQualityRules(workflow: SilverWorkflowRecord): GovernedQualityRule[] {\n  const rules: GovernedQualityRule[] = [];\n\n  for (const raw of workflow.quality_rules ?? []) {\n    const row = asRecord(raw);\n    if (!row) continue;\n\n    const legacyName = String(row.rule_name ?? row.name ?? row.rule_type ?? 'quality_rule');\n    const ruleType = String(row.rule_type ?? 'CUSTOM').toUpperCase();\n    const ruleId = String(row.rule_id ?? `qr_${legacyName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'quality_rule'}`);\n    const columns = Array.isArray(row.columns)\n      ? row.columns.map(String).filter(Boolean)\n      : [row.column_name, row.comparison_column].filter(Boolean).map(String);\n    const dimension = String(row.dimension ?? row.rule_dimension ?? 'VALIDITY') as QualityDimension;\n    const runtimeAction = String(row.runtime_action ?? 'WARN') as QualityRuntimeAction;\n\n    rules.push({\n      rule_id: ruleId,\n      name: legacyName,\n      version: typeof row.version === 'number' ? row.version : 1,\n      dimension,\n      rule_type: ruleType,\n      columns: Array.from(new Set(columns)),\n      parameters: asRecord(row.parameters) ?? asRecord(row.rule_parameters) ?? {},\n      expression: typeof row.expression === 'string' ? row.expression : null,\n      warning_threshold: typeof row.warning_threshold === 'number' ? row.warning_threshold : 0,\n      critical_threshold: typeof row.critical_threshold === 'number' ? row.critical_threshold : 1,\n      severity: String(row.severity ?? row.severity_level ?? 'MEDIUM'),\n      runtime_action: runtimeAction,\n      evidence:\n        typeof row.evidence === 'string'\n          ? row.evidence\n          : typeof row.agent_evidence === 'string' ? row.agent_evidence : null,\n      confidence:\n        typeof row.confidence === 'number'\n          ? row.confidence\n          : typeof row.agent_confidence === 'number' ? row.agent_confidence : null,\n      source: row.source === 'DERIVED_NL' || row.source === 'AI_RECOMMENDED' || row.source === 'MANUAL'\n        ? row.source\n        : row.agent_evidence != null ? 'AI_RECOMMENDED' : 'MANUAL',\n      status:\n        row.status === 'DRAFT' || row.status === 'PENDING_APPROVAL' || row.status === 'APPROVED' ||\n        row.status === 'REJECTED' || row.status === 'BLOCKED' || row.status === 'NEEDS_CLARIFICATION'\n          ? row.status\n          : workflow.quality_review ? 'APPROVED' : 'PENDING_APPROVAL',\n      active: row.active !== false && row.active_flag !== false,\n      approved_by: typeof row.approved_by === 'string' ? row.approved_by : null,\n      approved_at: typeof row.approved_at === 'string' ? row.approved_at : null,\n      metadata: asRecord(row.metadata) ?? {},\n    });\n  }\n\n  return rules;\n}\n\n'''
if helper not in text:
    if anchor not in text:
        raise SystemExit("No se encontró el ancla inferKeys en workflowResume.ts")
    text = text.replace(anchor, helper + anchor, 1)

old_assignment = "    approvedQualityRules: workflow.quality_rules ?? [],\n"
new_assignment = "    approvedQualityRules: governedQualityRules(workflow),\n    qualityRulesVersion: workflow.quality_rules_version ?? undefined,\n"
if old_assignment in text:
    text = text.replace(old_assignment, new_assignment, 1)
elif new_assignment not in text:
    raise SystemExit("No se encontró approvedQualityRules en workflowResume.ts")

PATH.write_text(text)
print("PASS: Quality Rule Designer 2A hydration recovery aplicado.")
print("Workflows legacy y gobernados se normalizan a GovernedQualityRule al reabrirse.")
