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


TYPES = "src/types.ts"
APP = "src/App.tsx"

replace(
    TYPES,
    """  qualityRuleProposals?: Array<Record<string, unknown>>;\n  approvedQualityRules?: Array<Record<string, unknown>>;\n  qualityReviewed?: boolean;\n""",
    """  qualityRuleProposals?: Array<Record<string, unknown>>;\n  approvedQualityRules?: GovernedQualityRule[];\n  qualityRulesVersion?: number;\n  qualityReviewed?: boolean;\n""",
)

replace(
    TYPES,
    """export interface BusinessRule {\n  name: string;\n  severity: 'HIGH' | 'MEDIUM' | 'LOW';\n  expression: string;\n}\n""",
    """export type QualityDimension =\n  | 'COMPLETENESS' | 'UNIQUENESS' | 'VALIDITY' | 'CONSISTENCY'\n  | 'REFERENTIAL' | 'TIMELINESS' | 'AGGREGATE' | 'BUSINESS';\n\nexport type QualityRuntimeAction = 'OBSERVE_ONLY' | 'WARN' | 'QUARANTINE' | 'BLOCK_LOAD';\n\nexport interface GovernedQualityRule {\n  rule_id: string;\n  name: string;\n  version: number;\n  dimension: QualityDimension;\n  rule_type: string;\n  columns: string[];\n  parameters: Record<string, unknown>;\n  expression?: string | null;\n  warning_threshold: number;\n  critical_threshold: number;\n  severity: string;\n  runtime_action: QualityRuntimeAction;\n  evidence?: string | null;\n  confidence?: number | null;\n  source: 'AI_RECOMMENDED' | 'MANUAL' | 'DERIVED_NL';\n  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'BLOCKED' | 'NEEDS_CLARIFICATION';\n  active: boolean;\n  approved_by?: string | null;\n  approved_at?: string | null;\n  metadata?: Record<string, unknown>;\n}\n\nexport interface BusinessRule {\n  name: string;\n  severity: 'HIGH' | 'MEDIUM' | 'LOW';\n  expression: string;\n}\n""",
)

replace(
    APP,
    """import type { CatalogField, GeneratedArtifact, MappingRule, StepId, WorkflowState } from './types';\n""",
    """import type {\n  CatalogField, GeneratedArtifact, GovernedQualityRule, MappingRule,\n  QualityDimension, QualityRuntimeAction, StepId, WorkflowState,\n} from './types';\n""",
)

replace(
    APP,
    """function proposalToBackendRule(proposal: Record<string, unknown>) {\n  const columnName = String(proposal.column_name ?? '');\n  const ruleType = String(proposal.rule_type ?? '');\n  return {\n    rule_name: `${columnName}_${ruleType.toLowerCase()}`,\n    rule_dimension: ruleType === 'UNIQUE' ? 'UNIQUENESS' : 'VALIDITY',\n    rule_type: ruleType,\n    column_name: columnName,\n    rule_parameters: (proposal.rule_parameters as Record<string, unknown> | undefined) ?? {},\n    warning_threshold: 0,\n    critical_threshold: 1,\n    severity_level: String(proposal.severity_level ?? 'MEDIUM'),\n    active_flag: true,\n    agent_evidence: proposal.evidence ?? null,\n    agent_confidence: proposal.confidence ?? null,\n  };\n}\n""",
    """function proposalToBackendRule(proposal: Record<string, unknown>): GovernedQualityRule {\n  const columnName = String(proposal.column_name ?? '');\n  const ruleType = String(proposal.rule_type ?? 'CUSTOM').toUpperCase();\n  const dimension: QualityDimension = ruleType === 'UNIQUE'\n    ? 'UNIQUENESS'\n    : ruleType === 'NOT_NULL' ? 'COMPLETENESS' : 'VALIDITY';\n  const ruleName = `${columnName || 'table'}_${ruleType.toLowerCase()}`;\n  return {\n    rule_id: `qr_${ruleName}`,\n    name: ruleName,\n    version: 1,\n    dimension,\n    rule_type: ruleType,\n    columns: columnName ? [columnName] : [],\n    parameters: (proposal.rule_parameters as Record<string, unknown> | undefined) ?? {},\n    warning_threshold: 0,\n    critical_threshold: 1,\n    severity: String(proposal.severity_level ?? 'MEDIUM'),\n    runtime_action: ruleType === 'NOT_NULL' || ruleType === 'UNIQUE' ? 'BLOCK_LOAD' : 'WARN',\n    evidence: proposal.evidence == null ? null : String(proposal.evidence),\n    confidence: typeof proposal.confidence === 'number' ? proposal.confidence : null,\n    source: 'AI_RECOMMENDED',\n    status: 'PENDING_APPROVAL',\n    active: true,\n    approved_by: null,\n    approved_at: null,\n    metadata: { current_status: proposal.current_status ?? null },\n  };\n}\n""",
)

replace(
    APP,
    """            onApproveProposal={(proposal, approved) => {\n              const rule = proposalToBackendRule(proposal);\n              setWorkflow((current) => {\n                const existing = current.approvedQualityRules ?? [];\n                const ruleName = String(rule.rule_name);\n                return {\n                  ...current,\n                  approvedQualityRules: approved\n                    ? [...existing.filter((item) => item.rule_name !== ruleName), rule]\n                    : existing.filter((item) => item.rule_name !== ruleName),\n                };\n              });\n            }}\n""",
    """            onApproveProposal={(proposal, approved) => {\n              const rule = proposalToBackendRule(proposal);\n              setWorkflow((current) => {\n                const existing = current.approvedQualityRules ?? [];\n                return {\n                  ...current,\n                  approvedQualityRules: approved\n                    ? [...existing.filter((item) => item.rule_id !== rule.rule_id), rule]\n                    : existing.filter((item) => item.rule_id !== rule.rule_id),\n                };\n              });\n            }}\n            onAddManualRule={(rule) => {\n              setWorkflow((current) => ({\n                ...current,\n                approvedQualityRules: [\n                  ...(current.approvedQualityRules ?? []).filter((item) => item.rule_id !== rule.rule_id),\n                  rule,\n                ],\n                ...demoWorkflowPatch('Regla manual agregada al Quality Rule Designer'),\n              }));\n            }}\n            onRemoveRule={(ruleId) => {\n              setWorkflow((current) => ({\n                ...current,\n                approvedQualityRules: (current.approvedQualityRules ?? []).filter((item) => item.rule_id !== ruleId),\n              }));\n            }}\n""",
)

replace(
    APP,
    """function RulesStep({\n  workflow,\n  onRecommend,\n  onApproveProposal,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onRecommend: () => void;\n  onApproveProposal: (proposal: Record<string, unknown>, approved: boolean) => void;\n  onNext: () => void;\n}) {\n  const proposals = workflow.qualityRuleProposals ?? [];\n  const approvedNames = new Set(\n    (workflow.approvedQualityRules ?? []).map((rule) => String(rule.rule_name)),\n  );\n""",
    """function RulesStep({\n  workflow,\n  onRecommend,\n  onApproveProposal,\n  onAddManualRule,\n  onRemoveRule,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onRecommend: () => void;\n  onApproveProposal: (proposal: Record<string, unknown>, approved: boolean) => void;\n  onAddManualRule: (rule: GovernedQualityRule) => void;\n  onRemoveRule: (ruleId: string) => void;\n  onNext: () => void;\n}) {\n  const proposals = workflow.qualityRuleProposals ?? [];\n  const approvedIds = new Set((workflow.approvedQualityRules ?? []).map((rule) => rule.rule_id));\n  const columns = workflow.sourceColumns ?? [];\n  const [manualType, setManualType] = useState('NOT_NULL');\n  const [manualDimension, setManualDimension] = useState<QualityDimension>('COMPLETENESS');\n  const [manualColumn, setManualColumn] = useState(columns[0]?.name ?? '');\n  const [manualSeverity, setManualSeverity] = useState('MEDIUM');\n  const [manualAction, setManualAction] = useState<QualityRuntimeAction>('WARN');\n  const [warningThreshold, setWarningThreshold] = useState(0);\n  const [criticalThreshold, setCriticalThreshold] = useState(1);\n\n  function addManual() {\n    if (!manualColumn) return;\n    if (criticalThreshold < warningThreshold) return;\n    const ruleName = `${manualColumn}_${manualType.toLowerCase()}`;\n    onAddManualRule({\n      rule_id: `qr_manual_${ruleName}`,\n      name: ruleName,\n      version: 1,\n      dimension: manualDimension,\n      rule_type: manualType,\n      columns: [manualColumn],\n      parameters: {},\n      warning_threshold: warningThreshold,\n      critical_threshold: criticalThreshold,\n      severity: manualSeverity,\n      runtime_action: manualAction,\n      evidence: 'Regla creada manualmente en Quality Rule Designer.',\n      confidence: null,\n      source: 'MANUAL',\n      status: 'PENDING_APPROVAL',\n      active: true,\n      approved_by: null,\n      approved_at: null,\n    });\n  }\n""",
)

replace(
    APP,
    """      <div className=\"sprintNote\">\n        <strong>Fallback deterministico</strong>\n        <span>\n          {toBackendQualityRules(workflow).length} reglas base disponibles si el agente no responde.\n          El sistema nunca aprueba automáticamente una recomendación.\n        </span>\n      </div>\n\n      {proposals.length ? (\n""",
    """      <div className=\"sprintNote\">\n        <strong>Quality Rule Designer gobernado</strong>\n        <span>\n          AI y reglas manuales usan el mismo contrato, permanecen PENDING_APPROVAL y solo se\n          vuelven ejecutables después del Quality Review.\n        </span>\n      </div>\n\n      <div className=\"formGrid three\">\n        <ContractSelectField label=\"Tipo de regla\" value={manualType}\n          options={['NOT_NULL', 'UNIQUE', 'ALLOWED_VALUES', 'VALUE_RANGE', 'REGEX']} onChange={setManualType} />\n        <ContractSelectField label=\"Dimensión\" value={manualDimension}\n          options={['COMPLETENESS', 'UNIQUENESS', 'VALIDITY', 'CONSISTENCY', 'REFERENTIAL', 'TIMELINESS', 'AGGREGATE', 'BUSINESS']}\n          onChange={(value) => setManualDimension(value as QualityDimension)} />\n        <ContractSelectField label=\"Columna\" value={manualColumn}\n          options={columns.map((column) => column.name)} onChange={setManualColumn} />\n        <ContractSelectField label=\"Severidad\" value={manualSeverity}\n          options={['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']} onChange={setManualSeverity} />\n        <ContractSelectField label=\"Runtime action\" value={manualAction}\n          options={['OBSERVE_ONLY', 'WARN', 'QUARANTINE', 'BLOCK_LOAD']}\n          onChange={(value) => setManualAction(value as QualityRuntimeAction)} />\n        <label className=\"field\"><span>Warning threshold</span><input type=\"number\" min=\"0\" value={warningThreshold}\n          onChange={(event) => setWarningThreshold(Number(event.target.value))} /></label>\n        <label className=\"field\"><span>Critical threshold</span><input type=\"number\" min=\"0\" value={criticalThreshold}\n          onChange={(event) => setCriticalThreshold(Number(event.target.value))} /></label>\n      </div>\n      <div className=\"actions\"><button onClick={addManual}>Agregar regla manual</button></div>\n      {criticalThreshold < warningThreshold && <small className=\"riskText\">Critical threshold debe ser mayor o igual que warning.</small>}\n\n      {proposals.length ? (\n""",
)

replace(
    APP,
    """            const backendRule = proposalToBackendRule(proposal);\n            const ruleName = String(backendRule.rule_name);\n            const approved = approvedNames.has(ruleName);\n""",
    """            const backendRule = proposalToBackendRule(proposal);\n            const ruleName = backendRule.name;\n            const approved = approvedIds.has(backendRule.rule_id);\n""",
)

replace(
    APP,
    """      <p className=\"catalogStatus\">\n        Aprobadas: {workflow.approvedQualityRules?.length ?? 0} · Workflow version backend:{' '}\n        {currentVersion(workflow)}\n      </p>\n      <button className=\"primary\" onClick={onNext}>Confirmar reglas aprobadas</button>\n""",
    """      {!!workflow.approvedQualityRules?.length && (\n        <div className=\"validationBox\">\n          <strong>Reglas seleccionadas para aprobación</strong>\n          {workflow.approvedQualityRules.map((rule) => (\n            <article key={rule.rule_id} className=\"checkOk\">\n              <strong>{rule.dimension} · {rule.name}</strong>\n              <span>{rule.rule_type} sobre {rule.columns.join(', ') || 'nivel tabla'} · {rule.severity}</span>\n              <small>Gate: {rule.runtime_action} · Warning {rule.warning_threshold} · Critical {rule.critical_threshold} · Origen {rule.source}</small>\n              <button className=\"dangerText\" onClick={() => onRemoveRule(rule.rule_id)}>Quitar</button>\n            </article>\n          ))}\n        </div>\n      )}\n      <p className=\"catalogStatus\">\n        Seleccionadas: {workflow.approvedQualityRules?.length ?? 0} · Quality Rules v{workflow.qualityRulesVersion ?? 'pendiente'} · Workflow v{currentVersion(workflow)}\n      </p>\n      <button className=\"primary\" onClick={onNext}>Confirmar reglas seleccionadas</button>\n""",
)

print("PASS: Quality Rule Designer 2A aplicado.")
print("AI + manual comparten contrato gobernado, thresholds, severidad y runtime action.")
