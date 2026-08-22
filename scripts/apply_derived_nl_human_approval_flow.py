from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


def append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text()
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + block.strip() + "\n")


# 1) Deterministic validation of Gemini's DERIVED_NL proposal.
tools = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_agents/tools.py"
replace_once(
    tools,
    "from .profile_service import BigQueryTableProfiler\n",
    "from modules.silver_intelligent_mapping.compiler import compile_pyspark_expression\n"
    "from modules.silver_intelligent_mapping.models import (\n"
    "    IntelligentMappingColumn,\n"
    "    MappingTransformation,\n"
    "    TransformationType,\n"
    ")\n\n"
    "from .profile_service import BigQueryTableProfiler\n",
)
replace_once(
    tools,
    "\ndef validate_business_rules(\n",
    '''\n\ndef validate_derived_nl_mapping_proposal(\n    columns_json: str,\n    natural_rule: str,\n    proposal_json: str,\n) -> dict[str, Any]:\n    \"\"\"Validate a Gemini-derived mapping against schema and executable whitelist.\"\"\"\n    columns = json.loads(columns_json)\n    proposal = json.loads(proposal_json)\n    if not isinstance(proposal, dict):\n        raise ValueError(\"La propuesta DERIVED_NL debe ser un objeto JSON\")\n\n    natural_rule = natural_rule.strip()\n    if not natural_rule:\n        raise ValueError(\"DERIVED_NL requiere una regla natural no vacía\")\n\n    schema = {\n        str(item.get(\"name\") or item.get(\"source_column\") or \"\"): str(\n            item.get(\"type\") or item.get(\"data_type\") or \"STRING\"\n        ).upper()\n        for item in columns\n        if isinstance(item, dict) and (item.get(\"name\") or item.get(\"source_column\"))\n    }\n    transformation_raw = proposal.get(\"transformation\")\n    if not isinstance(transformation_raw, dict):\n        raise ValueError(\"DERIVED_NL requiere transformation estructurada\")\n\n    transformation = MappingTransformation.model_validate(transformation_raw)\n    source_columns = list(transformation.source_columns)\n    unknown = sorted(set(source_columns) - set(schema))\n    if unknown:\n        raise ValueError(\n            \"La propuesta DERIVED_NL referencia columnas inexistentes: \" + \", \".join(unknown)\n        )\n\n    numeric_types = {\"INT64\", \"INTEGER\", \"FLOAT64\", \"FLOAT\", \"NUMERIC\", \"BIGNUMERIC\"}\n    if transformation.type == TransformationType.ARITHMETIC:\n        non_numeric = [name for name in source_columns if schema.get(name) not in numeric_types]\n        if non_numeric:\n            raise ValueError(\n                \"ARITHMETIC solo admite columnas numéricas: \" + \", \".join(non_numeric)\n            )\n\n    target_column = str(proposal.get(\"target_column\") or \"\").strip()\n    target_type = str(proposal.get(\"target_type\") or \"\").strip().upper()\n    if not target_column or not target_type:\n        raise ValueError(\"DERIVED_NL requiere target_column y target_type\")\n\n    column = IntelligentMappingColumn(\n        source_column=source_columns[0] if source_columns else None,\n        target_column=target_column,\n        target_type=target_type,\n        nullable=bool(proposal.get(\"nullable\", True)),\n        include=True,\n        transformation=transformation,\n        confidence=float(proposal.get(\"confidence\", 0.8)),\n        reason=str(proposal.get(\"reason\") or \"Interpretación DERIVED_NL validada contra el schema confirmado.\"),\n        risk=str(proposal.get(\"risk\") or \"La derivación requiere aprobación humana antes de persistirse.\"),\n        requires_approval=True,\n    )\n    compiled_preview = compile_pyspark_expression(column)\n\n    symbol = {\"ADD\": \"+\", \"SUBTRACT\": \"-\", \"MULTIPLY\": \"*\", \"DIVIDE\": \"/\"}.get(\n        str(transformation.parameters.get(\"operator\") or \"\").upper()\n    )\n    if transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 2 and symbol:\n        interpretation = (\n            f\"Entendí tu regla así: {target_column} = \"\n            f\"{source_columns[0]} {symbol} {source_columns[1]}.\"\n        )\n    else:\n        interpretation = (\n            f\"Entendí tu regla así: {target_column} se derivará con \"\n            f\"{transformation.type.value} usando {', '.join(source_columns)}.\"\n        )\n\n    normalized = {\n        \"source_column\": source_columns[0] if source_columns else None,\n        \"source_columns\": source_columns,\n        \"target_column\": target_column,\n        \"target_type\": target_type,\n        \"nullable\": column.nullable,\n        \"include\": True,\n        \"transformation\": transformation.model_dump(mode=\"json\"),\n        \"derivation_mode\": \"DERIVED_NL\",\n        \"natural_rule\": natural_rule,\n        \"confidence\": column.confidence,\n        \"reason\": column.reason,\n        \"risk\": column.risk,\n        \"requires_approval\": True,\n    }\n    return {\n        \"valid\": True,\n        \"proposal\": normalized,\n        \"interpretation\": interpretation,\n        \"compiled_preview\": compiled_preview,\n        \"human_confirmation_required\": True,\n        \"policy\": \"La propuesta no se persiste hasta confirmación humana explícita.\",\n    }\n\n\ndef validate_business_rules(\n''',
)

# 2) Mapping advisor knows the governed DERIVED_NL mode and validator tool.
agents = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_agents/agents.py"
replace_once(
    agents,
    "    recommend_column_mappings,\n",
    "    recommend_column_mappings,\n    validate_derived_nl_mapping_proposal,\n",
)
replace_once(
    agents,
    '''            "Solicitud gobernada: {request_json}. Perfil: {table_profile?}. "\n            "Usa recommend_column_mappings con las columnas reales de la solicitud. "\n            "No inventes columnas ni expresiones. Conserva source, target, tipo, "\n            "transformacion, confianza, razon y riesgo. Toda recomendacion queda "\n            "PENDING_APPROVAL. Devuelve exclusivamente JSON valido."\n        ),\n        tools=[recommend_column_mappings],\n''',
    '''            "Solicitud gobernada: {request_json}. Perfil: {table_profile?}. "\n            "Si context comienza con DERIVED_NL:, interpreta exactamente una derivación "\n            "usando solo columnas reales. No generes SQL, Python, PySpark ni expresiones libres. "\n            "Construye únicamente un contrato transformation estructurado y llama siempre "\n            "validate_derived_nl_mapping_proposal con columns_json, la regla natural exacta y "\n            "proposal_json. Devuelve exclusivamente el JSON retornado por esa tool. "\n            "Para solicitudes normales usa recommend_column_mappings. Toda recomendación queda "\n            "PENDING_APPROVAL y requiere confirmación humana."\n        ),\n        tools=[recommend_column_mappings, validate_derived_nl_mapping_proposal],\n''',
)

# 3) Router independently revalidates the final model output before exposing evidence.
router = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_agents/router.py"
replace_once(
    router,
    "from .tools import profile_selected_table, quality_rule_evidence, recommend_column_mappings\n",
    "from .tools import (\n"
    "    profile_selected_table,\n"
    "    quality_rule_evidence,\n"
    "    recommend_column_mappings,\n"
    "    validate_derived_nl_mapping_proposal,\n"
    ")\n",
)
replace_once(
    router,
    '    "mapping-advisor": ["profile_selected_table", "recommend_column_mappings"],\n',
    '    "mapping-advisor": ["profile_selected_table", "recommend_column_mappings", "validate_derived_nl_mapping_proposal"],\n',
)
replace_once(
    router,
    '''            elif agent_name == "mapping-advisor":\n                result.evidence = recommend_column_mappings(\n                    json.dumps(request.columns, ensure_ascii=False),\n                    json.dumps(profile, ensure_ascii=False),\n                )\n''',
    '''            elif agent_name == "mapping-advisor":\n                context = (request.context or "").strip()\n                if context.startswith("DERIVED_NL:"):\n                    natural_rule = context.split(":", 1)[1].strip()\n                    cleaned = result.output.strip()\n                    if cleaned.startswith("```"):\n                        cleaned = cleaned.replace("```json", "", 1).replace("```", "", 1).strip()\n                    parsed = json.loads(cleaned)\n                    if not isinstance(parsed, dict):\n                        raise ValueError("El mapping-advisor no devolvió un objeto JSON DERIVED_NL")\n                    candidate = parsed.get("proposal") if isinstance(parsed.get("proposal"), dict) else parsed\n                    result.evidence = validate_derived_nl_mapping_proposal(\n                        json.dumps(request.columns, ensure_ascii=False),\n                        natural_rule,\n                        json.dumps(candidate, ensure_ascii=False),\n                    )\n                else:\n                    result.evidence = recommend_column_mappings(\n                        json.dumps(request.columns, ensure_ascii=False),\n                        json.dumps(profile, ensure_ascii=False),\n                    )\n''',
)

# 4) Ensure Package/Spec payload preserves structured transformations and NL traceability.
app = ROOT / "src/App.tsx"
replace_once(
    app,
    '''      source_column: rule.sourceColumn,\n      transformation: toBackendTransformation(rule.transformationType),\n      include: true,\n''',
    '''      source_column: rule.sourceColumn || null,\n      source_columns: rule.sourceColumns?.length\n        ? rule.sourceColumns\n        : rule.sourceColumn ? [rule.sourceColumn] : [],\n      transformation: {\n        type: toBackendTransformation(rule.transformationType),\n        source_columns: rule.sourceColumns?.length\n          ? rule.sourceColumns\n          : rule.sourceColumn ? [rule.sourceColumn] : [],\n        parameters: rule.parameters ?? {},\n      },\n      derivation_mode: rule.derivationMode ?? null,\n      natural_rule: rule.naturalRule ?? null,\n      include: true,\n''',
)

# 5) Product state and UI flow: proposal is pending until explicit human confirmation.
replace_once(
    app,
    "  const [mappingImpactFingerprint, setMappingImpactFingerprint] = useState<string>();\n",
    "  const [mappingImpactFingerprint, setMappingImpactFingerprint] = useState<string>();\n"
    "  const [derivedNlProposal, setDerivedNlProposal] = useState<MappingRule>();\n"
    "  const [derivedNlInterpretation, setDerivedNlInterpretation] = useState<string>();\n",
)
replace_once(
    app,
    '''            impactAnalysis={mappingImpact}\n            onMappingChange={(rules) => {\n''',
    '''            derivedNlProposal={derivedNlProposal}\n            derivedNlInterpretation={derivedNlInterpretation}\n            onGenerateDerivedNl={async (intent) => {\n              const naturalRule = intent.trim();\n              if (!naturalRule) {\n                applyError(new Error('Escribe una regla en lenguaje natural antes de interpretarla.'));\n                return;\n              }\n              await runAction('Interpretando regla natural con mapping-advisor...', async () => {\n                const request = {\n                  ...buildAgentRequest(workflow),\n                  context: `DERIVED_NL:${naturalRule}`,\n                };\n                const response = await silverApi.runSilverAgent('mapping-advisor', request);\n                const evidence = response.evidence ?? parseAgentJson(response.output);\n                const proposal = evidence.proposal;\n                if (!evidence.valid || !proposal || typeof proposal !== 'object' || Array.isArray(proposal)) {\n                  throw new Error('El backend no validó una propuesta DERIVED_NL utilizable.');\n                }\n                const mapped = mappingFromRecommendation([proposal as Record<string, unknown>])[0];\n                if (!mapped || mapped.derivationMode !== 'DERIVED_NL') {\n                  throw new Error('La propuesta DERIVED_NL perdió su contrato de trazabilidad.');\n                }\n                setDerivedNlProposal(mapped);\n                setDerivedNlInterpretation(String(evidence.interpretation ?? 'Entendí tu regla y requiere confirmación.'));\n                setWorkflow((current) => ({\n                  ...current,\n                  agentSessionId: response.session_id,\n                  ...demoWorkflowPatch('Propuesta DERIVED_NL validada y pendiente de aprobación humana'),\n                  backendMessage: JSON.stringify(response),\n                }));\n              });\n            }}\n            onConfirmDerivedNl={() => {\n              if (!derivedNlProposal) return;\n              const currentRows = workflow.mappingRules?.length\n                ? workflow.mappingRules\n                : directMappingFromColumns(workflow.sourceColumns ?? []);\n              if (currentRows.some((row) => row.include && row.targetColumn === derivedNlProposal.targetColumn)) {\n                applyError(new Error(`Ya existe una columna destino ${derivedNlProposal.targetColumn}; ajusta la regla antes de confirmarla.`));\n                return;\n              }\n              setMappingImpact(undefined);\n              setMappingImpactFingerprint(undefined);\n              setWorkflow((current) => ({\n                ...current,\n                mappingRules: [...currentRows, derivedNlProposal],\n                mappingSource: 'DERIVED_NL',\n                ...demoWorkflowPatch('Derivación NL confirmada por usuario e incorporada al mapping'),\n              }));\n              setDerivedNlProposal(undefined);\n              setDerivedNlInterpretation(undefined);\n            }}\n            onRejectDerivedNl={() => {\n              setDerivedNlProposal(undefined);\n              setDerivedNlInterpretation(undefined);\n            }}\n            impactAnalysis={mappingImpact}\n            onMappingChange={(rules) => {\n''',
)

replace_once(
    app,
    '''  onGenerateAgent,\n  onMappingChange,\n  impactAnalysis,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  impactAnalysis?: MappingImpactResponse;\n  onNext: () => void;\n}) {\n''',
    '''  onGenerateAgent,\n  derivedNlProposal,\n  derivedNlInterpretation,\n  onGenerateDerivedNl,\n  onConfirmDerivedNl,\n  onRejectDerivedNl,\n  onMappingChange,\n  impactAnalysis,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  derivedNlProposal?: MappingRule;\n  derivedNlInterpretation?: string;\n  onGenerateDerivedNl: (intent: string) => void;\n  onConfirmDerivedNl: () => void;\n  onRejectDerivedNl: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  impactAnalysis?: MappingImpactResponse;\n  onNext: () => void;\n}) {\n''',
)
replace_once(
    app,
    "  const transformations = ['DIRECT', 'TRIM', 'UPPER', 'LOWER', 'CAST', 'EXCLUDE'];\n",
    "  const transformations = ['DIRECT', 'TRIM', 'UPPER', 'LOWER', 'CAST', 'ARITHMETIC', 'EXCLUDE'];\n"
    "  const [derivedIntent, setDerivedIntent] = useState('');\n",
)
replace_once(
    app,
    '''      <div className="mappingEditor">\n''',
    '''      <div className="sprintNote">\n        <strong>Crear campo derivado con lenguaje natural</strong>\n        <span>Gemini interpreta la intención; el backend valida el contrato y tú decides si se incorpora al mapping.</span>\n        <label className="field">\n          <span>Regla de negocio</span>\n          <textarea\n            value={derivedIntent}\n            onChange={(event) => setDerivedIntent(event.target.value)}\n            placeholder="Ejemplo: crear monto_neto restando descuento a monto_bruto"\n            rows={3}\n          />\n        </label>\n        <div className="actions">\n          <button onClick={() => onGenerateDerivedNl(derivedIntent)} disabled={!derivedIntent.trim()}>\n            Interpretar regla con Gemini\n          </button>\n        </div>\n      </div>\n\n      {derivedNlProposal && (\n        <div className="validationBox">\n          <strong>DERIVED_NL · PENDIENTE DE APROBACIÓN</strong>\n          <span>{derivedNlInterpretation ?? 'Entendí tu regla y la convertí a un contrato estructurado.'}</span>\n          <small>Destino: {derivedNlProposal.targetColumn} · Tipo: {derivedNlProposal.targetType}</small>\n          <small>Fuentes: {(derivedNlProposal.sourceColumns ?? [derivedNlProposal.sourceColumn]).filter(Boolean).join(', ')}</small>\n          <small>Transformación: {derivedNlProposal.transformationType}</small>\n          <small>Regla original: {derivedNlProposal.naturalRule}</small>\n          {derivedNlProposal.risk && <small className="riskText">Riesgo: {derivedNlProposal.risk}</small>}\n          <div className="actions">\n            <button className="primary" onClick={onConfirmDerivedNl}>Confirmar derivación</button>\n            <button onClick={onRejectDerivedNl}>Rechazar</button>\n          </div>\n        </div>\n      )}\n\n      <div className="mappingEditor">\n''',
)
replace_once(
    app,
    '''            <select\n              value={row.sourceColumn}\n              onChange={(event) => {\n                const field = sourceColumns.find((column) => column.name === event.target.value);\n                updateRow(index, {\n                  sourceColumn: event.target.value,\n                  targetColumn: row.targetColumn || event.target.value,\n                  targetType: field?.type ?? row.targetType,\n                  nullable: field?.mode !== 'REQUIRED',\n                });\n              }}\n            >\n              {sourceColumns.map((column) => (\n                <option key={column.name} value={column.name}>{column.name}</option>\n              ))}\n            </select>\n''',
    '''            {row.derivationMode === 'DERIVED_NL' ? (\n              <span title={row.naturalRule}>{(row.sourceColumns ?? [row.sourceColumn]).filter(Boolean).join(' + ')}</span>\n            ) : (\n              <select\n                value={row.sourceColumn}\n                onChange={(event) => {\n                  const field = sourceColumns.find((column) => column.name === event.target.value);\n                  updateRow(index, {\n                    sourceColumn: event.target.value,\n                    targetColumn: row.targetColumn || event.target.value,\n                    targetType: field?.type ?? row.targetType,\n                    nullable: field?.mode !== 'REQUIRED',\n                  });\n                }}\n              >\n                {sourceColumns.map((column) => (\n                  <option key={column.name} value={column.name}>{column.name}</option>\n                ))}\n              </select>\n            )}\n''',
)
replace_once(
    app,
    '''            <select\n              value={row.transformationType}\n              onChange={(event) => updateRow(index, {\n                transformationType: event.target.value,\n                include: event.target.value !== 'EXCLUDE',\n              })}\n            >\n''',
    '''            <select\n              value={row.transformationType}\n              disabled={row.derivationMode === 'DERIVED_NL'}\n              onChange={(event) => updateRow(index, {\n                transformationType: event.target.value,\n                include: event.target.value !== 'EXCLUDE',\n              })}\n            >\n''',
)
replace_once(
    app,
    '''              {row.requiresApproval && <em>REQUIERE APROBACION</em>}\n''',
    '''              {row.derivationMode === 'DERIVED_NL' && <small>DERIVED_NL · {row.naturalRule}</small>}\n              {row.requiresApproval && <em>REQUIERE APROBACION</em>}\n''',
)

# 6) Workflow source explicitly represents DERIVED_NL.
types = ROOT / "src/types.ts"
replace_once(
    types,
    "  mappingSource?: 'DIRECT' | 'DETERMINISTIC' | 'AGENT' | 'USER';\n",
    "  mappingSource?: 'DIRECT' | 'DETERMINISTIC' | 'AGENT' | 'USER' | 'DERIVED_NL';\n",
)

# 7) Tests for deterministic validator and package-facing structured contract.
test_path = ROOT / "backend/deployable/silver-refinement-agent/tests/test_derived_nl_advisor_validation.py"
if not test_path.exists():
    test_path.write_text('''import json\n\nimport pytest\n\nfrom modules.silver_agents.tools import validate_derived_nl_mapping_proposal\nfrom modules.silver_refinement.artifact_models import SilverColumn\n\n\nCOLUMNS = [\n    {"name": "monto_bruto", "type": "NUMERIC", "mode": "NULLABLE"},\n    {"name": "descuento", "type": "NUMERIC", "mode": "NULLABLE"},\n    {"name": "cliente", "type": "STRING", "mode": "NULLABLE"},\n]\n\n\ndef _proposal(source_columns=None, operator="SUBTRACT"):\n    return {\n        "target_column": "monto_neto",\n        "target_type": "NUMERIC",\n        "nullable": True,\n        "transformation": {\n            "type": "ARITHMETIC",\n            "source_columns": source_columns or ["monto_bruto", "descuento"],\n            "parameters": {"operator": operator},\n        },\n        "confidence": 0.91,\n        "reason": "Interpretación de la regla solicitada.",\n    }\n\n\ndef test_validator_preserves_exact_natural_rule_and_requires_human_confirmation():\n    natural_rule = "Crear monto_neto restando descuento a monto_bruto"\n    result = validate_derived_nl_mapping_proposal(\n        json.dumps(COLUMNS), natural_rule, json.dumps(_proposal())\n    )\n\n    assert result["valid"] is True\n    assert result["human_confirmation_required"] is True\n    assert result["proposal"]["derivation_mode"] == "DERIVED_NL"\n    assert result["proposal"]["natural_rule"] == natural_rule\n    assert result["proposal"]["transformation"]["parameters"]["operator"] == "SUBTRACT"\n    assert 'F.col("monto_bruto") - F.col("descuento")' in result["compiled_preview"]\n    assert result["interpretation"].startswith("Entendí tu regla así:")\n\n\ndef test_validator_rejects_unknown_source_column():\n    with pytest.raises(ValueError, match="columnas inexistentes"):\n        validate_derived_nl_mapping_proposal(\n            json.dumps(COLUMNS),\n            "Crear monto_neto",\n            json.dumps(_proposal(["monto_bruto", "columna_inventada"])),\n        )\n\n\ndef test_validator_rejects_non_numeric_arithmetic_source():\n    with pytest.raises(ValueError, match="solo admite columnas numéricas"):\n        validate_derived_nl_mapping_proposal(\n            json.dumps(COLUMNS),\n            "Restar cliente a monto bruto",\n            json.dumps(_proposal(["monto_bruto", "cliente"])),\n        )\n\n\ndef test_artifact_column_preserves_structured_derived_nl_transformation():\n    column = SilverColumn(\n        name="monto_neto",\n        data_type="NUMERIC",\n        source_column="monto_bruto",\n        source_columns=["monto_bruto", "descuento"],\n        transformation={\n            "type": "ARITHMETIC",\n            "source_columns": ["monto_bruto", "descuento"],\n            "parameters": {"operator": "SUBTRACT"},\n        },\n        derivation_mode="DERIVED_NL",\n        natural_rule="Crear monto_neto restando descuento a monto_bruto",\n        requires_approval=True,\n    )\n\n    normalized = column.normalized_transformation()\n    assert normalized.type.value == "ARITHMETIC"\n    assert normalized.source_columns == ["monto_bruto", "descuento"]\n    assert normalized.parameters["operator"] == "SUBTRACT"\n''')

print("PASS: flujo DERIVED_NL con aprobación humana aplicado.")
print("Gemini interpreta; backend revalida; UI exige confirmación; Spec/Package conserva contrato estructurado.")
