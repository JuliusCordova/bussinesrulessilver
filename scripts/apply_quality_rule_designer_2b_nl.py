from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1))


TOOLS = "backend/deployable/silver-refinement-agent/modules/silver_agents/tools.py"
AGENTS = "backend/deployable/silver-refinement-agent/modules/silver_agents/agents.py"
ROUTER = "backend/deployable/silver-refinement-agent/modules/silver_agents/router.py"
APP = "src/App.tsx"
TEST = ROOT / "backend/deployable/silver-refinement-agent/tests/test_quality_nl_rule_validation.py"

replace(
    TOOLS,
    """from modules.silver_intelligent_mapping.models import (\n    IntelligentMappingColumn,\n    MappingTransformation,\n    TransformationType,\n)\n\nfrom .profile_service import BigQueryTableProfiler\n""",
    """from modules.silver_intelligent_mapping.models import (\n    IntelligentMappingColumn,\n    MappingTransformation,\n    TransformationType,\n)\nfrom modules.silver_workflow.models import GovernedQualityRule\n\nfrom .profile_service import BigQueryTableProfiler\n""",
)

validator = r'''

def validate_quality_nl_rule_proposal(
    columns_json: str,
    natural_rule: str,
    proposal_json: str,
) -> dict[str, Any]:
    """Validate one LLM-interpreted quality rule against schema and an executable whitelist."""
    columns = json.loads(columns_json)
    proposal = json.loads(proposal_json)
    if not isinstance(proposal, dict):
        raise ValueError("La propuesta QUALITY_NL debe ser un objeto JSON")

    natural_rule = natural_rule.strip()
    if not natural_rule:
        raise ValueError("QUALITY_NL requiere una regla natural no vacía")

    schema = {
        str(item.get("name") or item.get("source_column") or ""): str(
            item.get("type") or item.get("data_type") or "STRING"
        ).upper()
        for item in columns
        if isinstance(item, dict) and (item.get("name") or item.get("source_column"))
    }

    rule_type = str(proposal.get("rule_type") or "").upper().strip()
    if rule_type not in SUPPORTED_RULE_TYPES:
        raise ValueError(
            "Tipo de regla no soportado para QUALITY_NL: " + (rule_type or "VACIO")
        )

    raw_columns = proposal.get("columns")
    if not isinstance(raw_columns, list):
        single = proposal.get("column_name")
        raw_columns = [single] if single else []
    rule_columns = [str(value).strip() for value in raw_columns if str(value).strip()]
    if len(rule_columns) != 1:
        raise ValueError("QUALITY_NL soporta exactamente una columna por regla en este checkpoint")
    unknown = sorted(set(rule_columns) - set(schema))
    if unknown:
        raise ValueError(
            "La propuesta QUALITY_NL referencia columnas inexistentes: " + ", ".join(unknown)
        )

    column_name = rule_columns[0]
    column_type = schema[column_name]
    parameters = proposal.get("parameters") or proposal.get("rule_parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError("QUALITY_NL requiere parameters como objeto")

    numeric_types = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL"}
    string_types = {"STRING", "BYTES"}

    if rule_type == "ALLOWED_VALUES":
        allowed = parameters.get("allowed_values")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("ALLOWED_VALUES requiere parameters.allowed_values no vacío")
    elif rule_type == "VALUE_RANGE":
        if column_type not in numeric_types:
            raise ValueError("VALUE_RANGE solo admite columnas numéricas")
        if parameters.get("min") is None and parameters.get("max") is None:
            raise ValueError("VALUE_RANGE requiere min y/o max")
        min_value = parameters.get("min")
        max_value = parameters.get("max")
        if min_value is not None and max_value is not None and float(min_value) > float(max_value):
            raise ValueError("VALUE_RANGE requiere min <= max")
    elif rule_type == "REGEX":
        if column_type not in string_types:
            raise ValueError("REGEX solo admite columnas STRING/BYTES")
        pattern = parameters.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("REGEX requiere parameters.pattern")

    dimension_default = {
        "NOT_NULL": "COMPLETENESS",
        "UNIQUE": "UNIQUENESS",
        "ALLOWED_VALUES": "VALIDITY",
        "VALUE_RANGE": "VALIDITY",
        "REGEX": "VALIDITY",
    }[rule_type]
    runtime_default = "BLOCK_LOAD" if rule_type in {"NOT_NULL", "UNIQUE"} else "WARN"
    warning_threshold = float(proposal.get("warning_threshold", 0))
    critical_threshold = float(proposal.get("critical_threshold", 1))
    if critical_threshold < warning_threshold:
        raise ValueError("critical_threshold debe ser mayor o igual que warning_threshold")

    name = str(proposal.get("name") or f"{column_name}_{rule_type.lower()}").strip()
    rule = GovernedQualityRule.model_validate({
        "rule_id": str(proposal.get("rule_id") or f"qr_nl_{column_name}_{rule_type.lower()}"),
        "name": name,
        "version": 1,
        "dimension": str(proposal.get("dimension") or dimension_default).upper(),
        "rule_type": rule_type,
        "columns": rule_columns,
        "parameters": parameters,
        "expression": None,
        "warning_threshold": warning_threshold,
        "critical_threshold": critical_threshold,
        "severity": str(proposal.get("severity") or proposal.get("severity_level") or "MEDIUM").upper(),
        "runtime_action": str(proposal.get("runtime_action") or runtime_default).upper(),
        "evidence": str(proposal.get("evidence") or "Regla interpretada desde lenguaje natural y validada contra el schema."),
        "confidence": float(proposal.get("confidence", 0.8)),
        "source": "DERIVED_NL",
        "status": "PENDING_APPROVAL",
        "active": True,
        "approved_by": None,
        "approved_at": None,
        "metadata": {
            **(proposal.get("metadata") if isinstance(proposal.get("metadata"), dict) else {}),
            "natural_rule": natural_rule,
            "validation_authority": "DETERMINISTIC_TOOL",
        },
    })

    if rule_type == "NOT_NULL":
        interpretation = f"Entendí tu regla así: {column_name} no debe contener valores nulos."
    elif rule_type == "UNIQUE":
        interpretation = f"Entendí tu regla así: {column_name} debe ser único."
    elif rule_type == "ALLOWED_VALUES":
        interpretation = (
            f"Entendí tu regla así: {column_name} solo puede tomar los valores "
            f"{parameters['allowed_values']}."
        )
    elif rule_type == "VALUE_RANGE":
        interpretation = (
            f"Entendí tu regla así: {column_name} debe cumplir el rango "
            f"min={parameters.get('min')} max={parameters.get('max')}."
        )
    else:
        interpretation = (
            f"Entendí tu regla así: {column_name} debe cumplir el patrón "
            f"{parameters.get('pattern')}."
        )

    return {
        "valid": True,
        "proposal": rule.model_dump(mode="json"),
        "interpretation": interpretation,
        "human_confirmation_required": True,
        "natural_rule": natural_rule,
        "policy": "El texto natural no es ejecutable; la propuesta estructurada requiere confirmación humana.",
    }
'''

replace(
    TOOLS,
    """def recommend_column_mappings(\n    columns_json: str,\n    profile_json: str = \"{}\",\n) -> dict[str, Any]:\n""",
    validator + "\n\ndef recommend_column_mappings(\n    columns_json: str,\n    profile_json: str = \"{}\",\n) -> dict[str, Any]:\n",
)

replace(
    AGENTS,
    """    validate_derived_nl_mapping_proposal,\n    quality_rule_evidence,\n""",
    """    validate_derived_nl_mapping_proposal,\n    validate_quality_nl_rule_proposal,\n    quality_rule_evidence,\n""",
)

replace(
    AGENTS,
    """        instruction=(\n            \"Solicitud: {request_json}. Perfil previo: {table_profile?}. \"\n            \"Si el perfil no está disponible, obtenlo con profile_selected_table. \"\n            \"Luego llama quality_rule_evidence usando el perfil JSON y \"\n            \"{business_keys_json}. Los campos críticos con nulos deben producir \"\n            \"NOT_NULL en estado FAILING; las claves deben evaluar NOT_NULL y UNIQUE. \"\n            \"Propón solo reglas con evidencia, déjalas PENDING_APPROVAL y devuelve \"\n            \"exclusivamente JSON válido.\"\n        ),\n        tools=[profile_selected_table, quality_rule_evidence],\n""",
    """        instruction=(\n            \"Solicitud: {request_json}. Perfil previo: {table_profile?}. \"\n            \"Si context comienza con QUALITY_NL:, interpreta exactamente una regla de calidad \"\n            \"usando solo columnas reales y uno de NOT_NULL, UNIQUE, ALLOWED_VALUES, VALUE_RANGE o REGEX. \"\n            \"No generes SQL, Python, PySpark ni expresiones libres. Construye solo un contrato estructurado \"\n            \"y llama siempre validate_quality_nl_rule_proposal con columns_json, la regla natural exacta \"\n            \"y proposal_json. Devuelve exclusivamente el JSON retornado por esa tool. \"\n            \"Para solicitudes normales, si falta perfil obtenlo con profile_selected_table y luego llama \"\n            \"quality_rule_evidence usando el perfil JSON y {business_keys_json}. Toda propuesta queda \"\n            \"PENDING_APPROVAL y requiere confirmación humana.\"\n        ),\n        tools=[profile_selected_table, quality_rule_evidence, validate_quality_nl_rule_proposal],\n""",
)

replace(
    ROUTER,
    """    recommend_column_mappings,\n    validate_derived_nl_mapping_proposal,\n)\n""",
    """    recommend_column_mappings,\n    validate_derived_nl_mapping_proposal,\n    validate_quality_nl_rule_proposal,\n)\n""",
)

replace(
    ROUTER,
    """    \"quality-rule-advisor\": [\n        \"profile_selected_table\",\n        \"quality_rule_evidence\",\n    ],\n""",
    """    \"quality-rule-advisor\": [\n        \"profile_selected_table\",\n        \"quality_rule_evidence\",\n        \"validate_quality_nl_rule_proposal\",\n    ],\n""",
)

replace(
    ROUTER,
    """            else:\n                result.evidence = quality_rule_evidence(\n                    json.dumps(profile, ensure_ascii=False),\n                    json.dumps(request.business_keys, ensure_ascii=False),\n                )\n""",
    """            else:\n                context = (request.context or \"\").strip()\n                if context.startswith(\"QUALITY_NL:\"):\n                    natural_rule = context.split(\":\", 1)[1].strip()\n                    cleaned = result.output.strip()\n                    if cleaned.startswith(\"```\"):\n                        cleaned = cleaned.replace(\"```json\", \"\", 1).replace(\"```\", \"\", 1).strip()\n                    parsed = json.loads(cleaned)\n                    if not isinstance(parsed, dict):\n                        raise ValueError(\"El quality-rule-advisor no devolvió un objeto JSON QUALITY_NL\")\n                    candidate = parsed.get(\"proposal\") if isinstance(parsed.get(\"proposal\"), dict) else parsed\n                    result.evidence = validate_quality_nl_rule_proposal(\n                        json.dumps(request.columns, ensure_ascii=False),\n                        natural_rule,\n                        json.dumps(candidate, ensure_ascii=False),\n                    )\n                else:\n                    result.evidence = quality_rule_evidence(\n                        json.dumps(profile, ensure_ascii=False),\n                        json.dumps(request.business_keys, ensure_ascii=False),\n                    )\n""",
)

replace(
    APP,
    """  const [derivedNlProposal, setDerivedNlProposal] = useState<MappingRule>();\n  const [derivedNlInterpretation, setDerivedNlInterpretation] = useState<string>();\n""",
    """  const [derivedNlProposal, setDerivedNlProposal] = useState<MappingRule>();\n  const [derivedNlInterpretation, setDerivedNlInterpretation] = useState<string>();\n  const [qualityNlProposal, setQualityNlProposal] = useState<GovernedQualityRule>();\n  const [qualityNlInterpretation, setQualityNlInterpretation] = useState<string>();\n""",
)

replace(
    APP,
    """            onAddManualRule={(rule) => {\n              setWorkflow((current) => ({\n                ...current,\n                approvedQualityRules: [\n                  ...(current.approvedQualityRules ?? []).filter((item) => item.rule_id !== rule.rule_id),\n                  rule,\n                ],\n                ...demoWorkflowPatch('Regla manual agregada al Quality Rule Designer'),\n              }));\n            }}\n""",
    """            qualityNlProposal={qualityNlProposal}\n            qualityNlInterpretation={qualityNlInterpretation}\n            onGenerateQualityNl={async (intent) => {\n              const naturalRule = intent.trim();\n              if (!naturalRule) {\n                applyError(new Error('Escribe una regla de calidad en lenguaje natural antes de interpretarla.'));\n                return;\n              }\n              await runAction('Interpretando regla de calidad con Gemini ADK...', async () => {\n                const response = await silverApi.runSilverAgent('quality-rule-advisor', {\n                  ...buildAgentRequest(workflow),\n                  context: `QUALITY_NL: ${naturalRule}`,\n                });\n                const output = response.evidence ?? parseAgentJson(response.output);\n                const proposal = output.proposal;\n                if (!proposal || typeof proposal !== 'object' || Array.isArray(proposal)) {\n                  throw new Error('El quality-rule-advisor no devolvió una propuesta gobernada.');\n                }\n                setQualityNlProposal(proposal as GovernedQualityRule);\n                setQualityNlInterpretation(String(output.interpretation ?? 'Entendí tu regla y la validé contra el schema.'));\n                setWorkflow((current) => ({\n                  ...current,\n                  agentSessionId: response.session_id,\n                  backendMessage: JSON.stringify(response),\n                }));\n              });\n            }}\n            onConfirmQualityNl={() => {\n              if (!qualityNlProposal) return;\n              setWorkflow((current) => ({\n                ...current,\n                approvedQualityRules: [\n                  ...(current.approvedQualityRules ?? []).filter((item) => item.rule_id !== qualityNlProposal.rule_id),\n                  qualityNlProposal,\n                ],\n                ...demoWorkflowPatch('Regla QUALITY_NL confirmada por usuario y agregada al Designer'),\n              }));\n              setQualityNlProposal(undefined);\n              setQualityNlInterpretation(undefined);\n            }}\n            onAddManualRule={(rule) => {\n              setWorkflow((current) => ({\n                ...current,\n                approvedQualityRules: [\n                  ...(current.approvedQualityRules ?? []).filter((item) => item.rule_id !== rule.rule_id),\n                  rule,\n                ],\n                ...demoWorkflowPatch('Regla manual agregada al Quality Rule Designer'),\n              }));\n            }}\n""",
)

replace(
    APP,
    """function RulesStep({\n  workflow,\n  onRecommend,\n  onApproveProposal,\n  onAddManualRule,\n  onRemoveRule,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onRecommend: () => void;\n  onApproveProposal: (proposal: Record<string, unknown>, approved: boolean) => void;\n  onAddManualRule: (rule: GovernedQualityRule) => void;\n  onRemoveRule: (ruleId: string) => void;\n  onNext: () => void;\n}) {\n""",
    """function RulesStep({\n  workflow,\n  onRecommend,\n  onApproveProposal,\n  qualityNlProposal,\n  qualityNlInterpretation,\n  onGenerateQualityNl,\n  onConfirmQualityNl,\n  onAddManualRule,\n  onRemoveRule,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onRecommend: () => void;\n  onApproveProposal: (proposal: Record<string, unknown>, approved: boolean) => void;\n  qualityNlProposal?: GovernedQualityRule;\n  qualityNlInterpretation?: string;\n  onGenerateQualityNl: (intent: string) => void;\n  onConfirmQualityNl: () => void;\n  onAddManualRule: (rule: GovernedQualityRule) => void;\n  onRemoveRule: (ruleId: string) => void;\n  onNext: () => void;\n}) {\n""",
)

replace(
    APP,
    """  const [criticalThreshold, setCriticalThreshold] = useState(1);\n\n  function addManual() {\n""",
    """  const [criticalThreshold, setCriticalThreshold] = useState(1);\n  const [qualityNlIntent, setQualityNlIntent] = useState('');\n\n  function addManual() {\n""",
)

replace(
    APP,
    """      <div className=\"formGrid three\">\n        <ContractSelectField label=\"Tipo de regla\" value={manualType}\n""",
    """      <div className=\"validationBox\">\n        <strong>Regla en lenguaje natural</strong>\n        <label className=\"field\">\n          <span>Describe la regla que quieres controlar</span>\n          <textarea\n            rows={3}\n            value={qualityNlIntent}\n            placeholder=\"Ejemplo: monto_total debe estar entre 0 y 100000\"\n            onChange={(event) => setQualityNlIntent(event.target.value)}\n          />\n        </label>\n        <div className=\"actions\">\n          <button onClick={() => onGenerateQualityNl(qualityNlIntent)}>Interpretar regla con AI</button>\n        </div>\n        {qualityNlProposal && (\n          <article className=\"checkOk\">\n            <strong>{qualityNlInterpretation ?? 'Entendí tu regla así:'}</strong>\n            <span>{qualityNlProposal.dimension} · {qualityNlProposal.rule_type} · {qualityNlProposal.columns.join(', ')}</span>\n            <small>Gate {qualityNlProposal.runtime_action} · Origen DERIVED_NL · Estado PENDING_APPROVAL</small>\n            <div className=\"actions\">\n              <button className=\"primary\" onClick={() => { onConfirmQualityNl(); setQualityNlIntent(''); }}>Confirmar regla interpretada</button>\n            </div>\n          </article>\n        )}\n        <small>El texto natural es evidencia de intención; solo el contrato estructurado validado puede aprobarse.</small>\n      </div>\n\n      <div className=\"formGrid three\">\n        <ContractSelectField label=\"Tipo de regla\" value={manualType}\n""",
)

if not TEST.exists():
    TEST.write_text(r'''import json

import pytest

from modules.silver_agents.tools import validate_quality_nl_rule_proposal


COLUMNS = [
    {"name": "monto_total", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "estado", "type": "STRING", "mode": "NULLABLE"},
    {"name": "cliente_id", "type": "STRING", "mode": "NULLABLE"},
]


def test_quality_nl_value_range_is_structured_and_requires_confirmation():
    result = validate_quality_nl_rule_proposal(
        json.dumps(COLUMNS),
        "monto_total debe estar entre 0 y 100000",
        json.dumps({
            "rule_type": "VALUE_RANGE",
            "columns": ["monto_total"],
            "parameters": {"min": 0, "max": 100000},
            "severity": "HIGH",
            "runtime_action": "QUARANTINE",
            "confidence": 0.93,
        }),
    )
    assert result["valid"] is True
    assert result["human_confirmation_required"] is True
    assert result["proposal"]["source"] == "DERIVED_NL"
    assert result["proposal"]["status"] == "PENDING_APPROVAL"
    assert result["proposal"]["expression"] is None
    assert result["proposal"]["metadata"]["natural_rule"] == "monto_total debe estar entre 0 y 100000"
    assert result["interpretation"].startswith("Entendí tu regla así:")


def test_quality_nl_rejects_unknown_column():
    with pytest.raises(ValueError, match="columnas inexistentes"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "campo_falso no debe ser nulo",
            json.dumps({"rule_type": "NOT_NULL", "columns": ["campo_falso"]}),
        )


def test_quality_nl_rejects_unsupported_free_expression_type():
    with pytest.raises(ValueError, match="Tipo de regla no soportado"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "ejecuta esta expresión libre",
            json.dumps({"rule_type": "SQL_EXPRESSION", "columns": ["monto_total"], "expression": "DROP TABLE x"}),
        )


def test_quality_nl_regex_requires_string_column():
    with pytest.raises(ValueError, match="REGEX solo admite"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "monto_total debe cumplir un patrón",
            json.dumps({"rule_type": "REGEX", "columns": ["monto_total"], "parameters": {"pattern": "^[0-9]+$"}}),
        )
''')

print("PASS: Quality Rule Designer 2B QUALITY_NL aplicado.")
print("Gemini interpreta; backend valida whitelist/schema; UI exige confirmación humana.")
