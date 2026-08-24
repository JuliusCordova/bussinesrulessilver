from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "src" / "api.ts"
APP = ROOT / "src" / "App.tsx"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"No se encontró marcador para {label}")
    return text.replace(old, new, 1)


api = API.read_text(encoding="utf-8")
api = replace_once(
    api,
    "  runSilverAgent: (agentName: SilverAgentName, payload: SilverAgentRunRequest) =>\n    request<SilverAgentRunResponse>(`/silver-agents/${agentName}/run`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n",
    "  runSilverAgent: (agentName: SilverAgentName, payload: SilverAgentRunRequest) =>\n    request<SilverAgentRunResponse>(`/silver-agents/${agentName}/run`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n  validateSrl: (payload: SrlValidationRequest) =>\n    request<SrlValidationResponse>('/silver-rules/validate', {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n",
    "api validateSrl",
)
api = replace_once(
    api,
    "export interface SilverAgentRunResponse {\n  agent_name: string;\n  session_id: string;\n  status: string;\n  output: string;\n  events: number;\n  evidence?: Record<string, unknown> | null;\n}\n\n",
    "export interface SilverAgentRunResponse {\n  agent_name: string;\n  session_id: string;\n  status: string;\n  output: string;\n  events: number;\n  evidence?: Record<string, unknown> | null;\n}\n\nexport interface SrlValidationRequest {\n  srl: string;\n  schema: Array<{ name: string; type: string }>;\n}\n\nexport interface SrlValidationResponse {\n  valid: boolean;\n  srl_version: string;\n  normalized_srl: string;\n  ast: Record<string, unknown>;\n  governed_contract: GovernedQualityRule | Record<string, unknown>;\n}\n\n",
    "api SRL interfaces",
)
API.write_text(api, encoding="utf-8")

app = APP.read_text(encoding="utf-8")
app = replace_once(
    app,
    "  const [regexPattern, setRegexPattern] = useState('');\n\n",
    "  const [regexPattern, setRegexPattern] = useState('');\n  const [ruleMode, setRuleMode] = useState<'BUILDER' | 'SRL'>('BUILDER');\n  const [srlText, setSrlText] = useState('CHECK ramo_id NOT_NULL\\nON_FAIL BLOCK_LOAD');\n  const [srlPreview, setSrlPreview] = useState<GovernedQualityRule | null>(null);\n  const [srlNormalized, setSrlNormalized] = useState('');\n  const [srlError, setSrlError] = useState('');\n  const [srlLoading, setSrlLoading] = useState(false);\n\n",
    "RulesStep SRL state",
)
app = replace_once(
    app,
    "  const parameterError = manualParameterError();\n\n  function addManual",
    "  const parameterError = manualParameterError();\n\n  async function validateSrlRule() {\n    setSrlLoading(true);\n    setSrlError('');\n    setSrlPreview(null);\n    try {\n      const result = await silverApi.validateSrl({\n        srl: srlText,\n        schema: columns.map((column) => ({ name: column.name, type: column.type })),\n      });\n      const contract = result.governed_contract as GovernedQualityRule;\n      setSrlPreview(contract);\n      setSrlNormalized(result.normalized_srl);\n    } catch (error) {\n      setSrlNormalized('');\n      setSrlError(normalizeError(error).summary);\n    } finally {\n      setSrlLoading(false);\n    }\n  }\n\n  function addValidatedSrlRule() {\n    if (!srlPreview) return;\n    onAddManualRule({\n      ...srlPreview,\n      source: 'MANUAL',\n      status: 'PENDING_APPROVAL',\n      active: true,\n      metadata: {\n        ...(srlPreview.metadata ?? {}),\n        creation_mode: 'SRL',\n        normalized_srl: srlNormalized,\n      },\n    });\n    setSrlPreview(null);\n    setSrlNormalized('');\n  }\n\n  function addManual",
    "RulesStep SRL handlers",
)
old_block = """      <div className=\"validationBox\">\n        <strong>Regla en lenguaje natural</strong>\n        <label className=\"field\">\n          <span>Describe la regla que quieres controlar</span>\n          <textarea\n            rows={3}\n            value={qualityNlIntent}\n            placeholder=\"Ejemplo: monto_total debe estar entre 0 y 100000\"\n            onChange={(event) => setQualityNlIntent(event.target.value)}\n          />\n        </label>\n        <div className=\"actions\">\n          <button onClick={() => onGenerateQualityNl(qualityNlIntent)}>Interpretar regla con AI</button>\n        </div>\n        {qualityNlProposal && (\n          <article className=\"checkOk\">\n            <strong>{qualityNlInterpretation ?? 'Entendí tu regla así:'}</strong>\n            <span>{qualityNlProposal.dimension} · {qualityNlProposal.rule_type} · {qualityNlProposal.columns.join(', ')}</span>\n            <small>Gate {qualityNlProposal.runtime_action} · Origen DERIVED_NL · Estado PENDING_APPROVAL</small>\n            <div className=\"actions\">\n              <button className=\"primary\" onClick={() => { onConfirmQualityNl(); setQualityNlIntent(''); }}>Confirmar regla interpretada</button>\n            </div>\n          </article>\n        )}\n        <small>El texto natural es evidencia de intención; solo el contrato estructurado validado puede aprobarse.</small>\n      </div>\n\n"""
new_block = """      <div className=\"validationBox\">\n        <strong>Crear regla de calidad</strong>\n        <span>Primero estabilizamos dos caminos determinísticos. La IA se conectará después como traductor hacia SRL.</span>\n        <div className=\"actions\">\n          <button className={ruleMode === 'BUILDER' ? 'primary' : ''} onClick={() => setRuleMode('BUILDER')}>Constructor visual</button>\n          <button className={ruleMode === 'SRL' ? 'primary' : ''} onClick={() => setRuleMode('SRL')}>Pseudocódigo SRL</button>\n        </div>\n      </div>\n\n      {ruleMode === 'SRL' && (\n        <div className=\"validationBox\">\n          <strong>Silver Rule Language · CHECK</strong>\n          <label className=\"field\">\n            <span>Regla SRL</span>\n            <textarea\n              rows={5}\n              value={srlText}\n              onChange={(event) => { setSrlText(event.target.value); setSrlPreview(null); setSrlError(''); }}\n              placeholder={'CHECK moneda IN [\"PEN\", \"USD\"]\\nON_FAIL WARN'}\n            />\n          </label>\n          <small>Operadores v1.0: NOT_NULL · UNIQUE · IN · BETWEEN · MATCHES. ON_FAIL es obligatorio.</small>\n          <div className=\"actions\">\n            <button className=\"primary\" disabled={!srlText.trim() || srlLoading} onClick={() => void validateSrlRule()}>\n              {srlLoading ? 'Validando...' : 'Validar SRL'}\n            </button>\n            <button onClick={() => setSrlText('CHECK ramo_id NOT_NULL\\nON_FAIL BLOCK_LOAD')}>Ejemplo NOT_NULL</button>\n            <button onClick={() => setSrlText('CHECK moneda IN [\"PEN\", \"USD\"]\\nON_FAIL WARN')}>Ejemplo IN</button>\n          </div>\n          {srlError && <small className=\"riskText\">{srlError}</small>}\n          {srlPreview && (\n            <article className=\"checkOk\">\n              <strong>SRL válida · lista para agregar</strong>\n              <span>{srlNormalized}</span>\n              <small>{srlPreview.dimension} · {srlPreview.rule_type} · {srlPreview.columns.join(', ')}</small>\n              <small>Gate {srlPreview.runtime_action} · Estado {srlPreview.status}</small>\n              {Object.keys(srlPreview.parameters ?? {}).length > 0 && <small>Parámetros: {JSON.stringify(srlPreview.parameters)}</small>}\n              <div className=\"actions\">\n                <button className=\"primary\" onClick={addValidatedSrlRule}>Agregar regla validada</button>\n              </div>\n            </article>\n          )}\n        </div>\n      )}\n\n      {ruleMode === 'BUILDER' && (\n        <div className=\"validationBox\">\n          <strong>Constructor visual determinístico</strong>\n          <span>Selecciona el contrato; los parámetros aparecen según el tipo de regla.</span>\n        </div>\n      )}\n\n"""
app = replace_once(app, old_block, new_block, "RulesStep AI block -> deterministic modes")
APP.write_text(app, encoding="utf-8")

print("SRL Quality UI applied: Builder + direct SRL validation")
