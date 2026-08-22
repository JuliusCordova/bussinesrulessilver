from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:140]!r}")
    target.write_text(text.replace(old, new, 1))


# 1) Backend models: deterministic read-only impact contract.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py",
    """class SaveSilverMappingRequest(BaseModel):\n    expected_version: int = Field(ge=1)\n    target: SilverTargetReference\n    columns: list[SilverMappingColumn] = Field(min_length=1)\n    edited_by: str = Field(min_length=2, max_length=200)\n    change_reason: str = Field(min_length=2, max_length=2000)\n\n    @model_validator(mode=\"after\")\n    def validate_unique_target_columns(self) -> \"SaveSilverMappingRequest\":\n        names = [column.name for column in self.columns]\n        if len(names) != len(set(names)):\n            raise ValueError(\"Cada columna destino Silver debe tener un nombre único\")\n        return self\n\n\nclass ReviewQualityRequest(BaseModel):""",
    """class MappingImpactRequest(BaseModel):\n    expected_version: int = Field(ge=1)\n    target: SilverTargetReference\n    columns: list[SilverMappingColumn] = Field(min_length=1)\n\n    @model_validator(mode=\"after\")\n    def validate_unique_target_columns(self) -> \"MappingImpactRequest\":\n        names = [column.name for column in self.columns]\n        if len(names) != len(set(names)):\n            raise ValueError(\"Cada columna destino Silver debe tener un nombre único\")\n        return self\n\n\nclass MappingImpactResponse(BaseModel):\n    workflow_id: str\n    current_workflow_version: int = Field(ge=1)\n    current_mapping_version: int | None = Field(default=None, ge=1)\n    proposed_mapping_version: int = Field(ge=1)\n    impact_level: str\n    has_changes: bool\n    added_columns: list[str] = Field(default_factory=list)\n    removed_columns: list[str] = Field(default_factory=list)\n    modified_columns: list[str] = Field(default_factory=list)\n    affected_quality_rules: list[str] = Field(default_factory=list)\n    downstream_invalidations: list[str] = Field(default_factory=list)\n    summary: str\n\n\nclass SaveSilverMappingRequest(BaseModel):\n    expected_version: int = Field(ge=1)\n    target: SilverTargetReference\n    columns: list[SilverMappingColumn] = Field(min_length=1)\n    edited_by: str = Field(min_length=2, max_length=200)\n    change_reason: str = Field(min_length=2, max_length=2000)\n\n    @model_validator(mode=\"after\")\n    def validate_unique_target_columns(self) -> \"SaveSilverMappingRequest\":\n        names = [column.name for column in self.columns]\n        if len(names) != len(set(names)):\n            raise ValueError(\"Cada columna destino Silver debe tener un nombre único\")\n        return self\n\n\nclass ReviewQualityRequest(BaseModel):""",
)

# 2) Service imports + deterministic analyzer. No mutation occurs here.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    """    GenerateBusinessRulesRequest,\n    ReviewQualityRequest,""",
    """    GenerateBusinessRulesRequest,\n    MappingImpactRequest,\n    MappingImpactResponse,\n    ReviewQualityRequest,""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    """    def save_mapping_version(self, workflow_id: str, request: SaveSilverMappingRequest) -> SilverWorkflowRecord:\n        current = self._require_version(workflow_id, request.expected_version)""",
    """    @staticmethod\n    def _mapping_shape(raw: dict[str, object]) -> dict[str, object]:\n        return {\n            \"name\": raw.get(\"name\") or raw.get(\"target_column\"),\n            \"data_type\": raw.get(\"data_type\") or raw.get(\"target_type\"),\n            \"nullable\": raw.get(\"nullable\", True),\n            \"source_column\": raw.get(\"source_column\") or raw.get(\"sourceColumn\"),\n            \"transformation\": raw.get(\"transformation\") or raw.get(\"transformation_type\") or raw.get(\"transformationType\"),\n        }\n\n    @staticmethod\n    def _quality_rule_columns(rule: dict[str, object]) -> set[str]:\n        columns: set[str] = set()\n        for key in (\"column_name\", \"column\", \"columns\", \"source_columns\", \"target_columns\"):\n            value = rule.get(key)\n            if isinstance(value, str) and value:\n                columns.add(value)\n            elif isinstance(value, list):\n                columns.update(str(item) for item in value if item)\n        return columns\n\n    def analyze_mapping_impact(self, workflow_id: str, request: MappingImpactRequest) -> MappingImpactResponse:\n        current = self._require_version(workflow_id, request.expected_version)\n        if not current.source_confirmed or current.schema_context is None:\n            raise WorkflowStateConflictError(\"La fuente y el esquema deben estar confirmados antes de analizar el mapping\")\n\n        previous = {\n            str(shape[\"name\"]): shape\n            for raw in current.mapping_rules\n            if (shape := self._mapping_shape(raw)).get(\"name\")\n        }\n        proposed = {\n            column.name: self._mapping_shape(column.model_dump(mode=\"json\"))\n            for column in request.columns\n        }\n\n        added = sorted(set(proposed) - set(previous))\n        removed = sorted(set(previous) - set(proposed))\n        modified = sorted(\n            name for name in set(previous) & set(proposed)\n            if previous[name] != proposed[name]\n        )\n        changed_columns = set(added) | set(removed) | set(modified)\n\n        affected_rules: list[str] = []\n        for rule in current.quality_rules:\n            if not isinstance(rule, dict):\n                continue\n            if self._quality_rule_columns(rule) & changed_columns:\n                affected_rules.append(str(rule.get(\"rule_name\") or rule.get(\"name\") or \"regla_sin_nombre\"))\n\n        has_changes = bool(changed_columns)\n        invalidations = [\n            \"SPECIFICATION\",\n            \"QUALITY_REVIEW\",\n            \"ARTIFACT_PACKAGE\",\n            \"GOVERNANCE\",\n            \"EXECUTION\",\n            \"VALIDATION\",\n        ] if has_changes else []\n\n        if removed or affected_rules:\n            impact_level = \"HIGH\"\n        elif modified:\n            impact_level = \"MEDIUM\"\n        elif added:\n            impact_level = \"LOW\"\n        else:\n            impact_level = \"NONE\"\n\n        summary = (\n            f\"{len(added)} agregadas, {len(removed)} eliminadas, {len(modified)} modificadas; \"\n            f\"{len(affected_rules)} reglas de calidad afectadas.\"\n            if has_changes\n            else \"No se detectaron cambios materiales frente al mapping persistido.\"\n        )\n        return MappingImpactResponse(\n            workflow_id=workflow_id,\n            current_workflow_version=current.version,\n            current_mapping_version=current.mapping_version,\n            proposed_mapping_version=(current.mapping_version or 0) + 1,\n            impact_level=impact_level,\n            has_changes=has_changes,\n            added_columns=added,\n            removed_columns=removed,\n            modified_columns=modified,\n            affected_quality_rules=sorted(set(affected_rules)),\n            downstream_invalidations=invalidations,\n            summary=summary,\n        )\n\n    def save_mapping_version(self, workflow_id: str, request: SaveSilverMappingRequest) -> SilverWorkflowRecord:\n        current = self._require_version(workflow_id, request.expected_version)""",
)

# 3) Router endpoint: preview only, same optimistic workflow version gate.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    """    GenerateBusinessRulesRequest,\n    ReviewQualityRequest,""",
    """    GenerateBusinessRulesRequest,\n    MappingImpactRequest,\n    MappingImpactResponse,\n    ReviewQualityRequest,""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    """@router.put(\"/{workflow_id}/mapping\", response_model=SilverWorkflowRecord)""",
    """@router.post(\"/{workflow_id}/mapping/impact\", response_model=MappingImpactResponse)\ndef analyze_workflow_mapping_impact(workflow_id: str, request: MappingImpactRequest, business: WorkflowBusinessOperation = Depends(require_workflow_mapping)) -> MappingImpactResponse:\n    try:\n        result = business.workflow_service.analyze_mapping_impact(workflow_id, request)\n        business.record_success(workflow_id=workflow_id)\n        return result\n    except WorkflowNotFoundError as exc:\n        raise _not_found(exc) from exc\n    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:\n        raise _conflict(exc) from exc\n    except ValueError as exc:\n        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc\n\n\n@router.put(\"/{workflow_id}/mapping\", response_model=SilverWorkflowRecord)""",
)

# 4) Frontend API.
replace(
    "src/api.ts",
    """  saveMapping: (workflowId: string, payload: unknown) =>\n    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/mapping`, {""",
    """  analyzeMappingImpact: (workflowId: string, payload: unknown) =>\n    request<MappingImpactResponse>(`/silver-workflows/${workflowId}/mapping/impact`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n  saveMapping: (workflowId: string, payload: unknown) =>\n    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/mapping`, {""",
)
replace(
    "src/api.ts",
    """export interface MappingRecommendationResponse {""",
    """export interface MappingImpactResponse {\n  workflow_id: string;\n  current_workflow_version: number;\n  current_mapping_version?: number | null;\n  proposed_mapping_version: number;\n  impact_level: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | string;\n  has_changes: boolean;\n  added_columns: string[];\n  removed_columns: string[];\n  modified_columns: string[];\n  affected_quality_rules: string[];\n  downstream_invalidations: string[];\n  summary: string;\n}\n\nexport interface MappingRecommendationResponse {""",
)

# 5) App imports + local impact gate state.
replace(
    "src/App.tsx",
    """  type CatalogTableDetail,\n  type SilverAgentDescriptor,""",
    """  type CatalogTableDetail,\n  type MappingImpactResponse,\n  type SilverAgentDescriptor,""",
)
replace(
    "src/App.tsx",
    """  const [showDataprocConfirm, setShowDataprocConfirm] = useState(false);""",
    """  const [showDataprocConfirm, setShowDataprocConfirm] = useState(false);\n  const [mappingImpact, setMappingImpact] = useState<MappingImpactResponse>();\n  const [mappingImpactPendingRules, setMappingImpactPendingRules] = useState<MappingRule[]>();""",
)

# Reset stale impact whenever the user edits the mapping.
replace(
    "src/App.tsx",
    """            onMappingChange={(rules) => {\n              setWorkflow((current) => ({""",
    """            onMappingChange={(rules) => {\n              setMappingImpact(undefined);\n              setMappingImpactPendingRules(undefined);\n              setWorkflow((current) => ({""",
)

# First click on resumed workflow = preview; second explicit confirm = persist.
replace(
    "src/App.tsx",
    """              if (workflow.resumedFromBackend && workflow.workflowId) {\n                await runAction('Persistiendo nueva versión gobernada del mapping...', async () => {\n                  const includedRules = rules.filter((rule) => rule.include);\n                  const updated = await silverApi.saveMapping(workflow.workflowId!, {""",
    """              if (workflow.resumedFromBackend && workflow.workflowId) {\n                const includedRules = rules.filter((rule) => rule.include);\n                const payload = {\n                  expected_version: currentVersion(workflow),\n                  target: {\n                    project_id: workflow.projectId ?? seedSource.projectId,\n                    dataset_id: workflow.targetDataset ?? seedSource.targetDataset,\n                    table_id: workflow.targetTable ?? seedSource.targetTable,\n                  },\n                  columns: includedRules.map((rule) => ({\n                    name: rule.targetColumn,\n                    data_type: rule.targetType,\n                    nullable: rule.nullable,\n                    source_column: rule.sourceColumn || null,\n                    transformation: toBackendTransformation(rule.transformationType),\n                  })),\n                };\n\n                const impactMatchesCurrentProposal = mappingImpactPendingRules === rules;\n                if (!mappingImpact || !impactMatchesCurrentProposal) {\n                  await runAction('Analizando impacto del cambio de mapping...', async () => {\n                    const impact = await silverApi.analyzeMappingImpact(workflow.workflowId!, payload);\n                    setMappingImpact(impact);\n                    setMappingImpactPendingRules(rules);\n                  });\n                  return;\n                }\n                if (!mappingImpact.has_changes) {\n                  applyError(new Error('No se detectaron cambios materiales frente al mapping persistido.'));\n                  return;\n                }\n\n                await runAction('Persistiendo nueva versión gobernada del mapping...', async () => {\n                  const updated = await silverApi.saveMapping(workflow.workflowId!, {\n                    ...payload,""",
)
# Remove duplicated payload fragment left by the original save call.
replace(
    "src/App.tsx",
    """                    expected_version: currentVersion(workflow),\n                    target: {\n                      project_id: workflow.projectId ?? seedSource.projectId,\n                      dataset_id: workflow.targetDataset ?? seedSource.targetDataset,\n                      table_id: workflow.targetTable ?? seedSource.targetTable,\n                    },\n                    columns: includedRules.map((rule) => ({\n                      name: rule.targetColumn,\n                      data_type: rule.targetType,\n                      nullable: rule.nullable,\n                      source_column: rule.sourceColumn || null,\n                      transformation: toBackendTransformation(rule.transformationType),\n                    })),\n                    edited_by: REQUESTED_BY,""",
    """                    edited_by: REQUESTED_BY,""",
)
replace(
    "src/App.tsx",
    """                  setWorkflow((current) => ({\n                    ...current,""",
    """                  setMappingImpact(undefined);\n                  setMappingImpactPendingRules(undefined);\n                  setWorkflow((current) => ({\n                    ...current,""",
)

# 6) MappingStep accepts and renders impact analysis.
replace(
    "src/App.tsx",
    """            onNext={async () => {""",
    """            impactAnalysis={mappingImpact}\n            onNext={async () => {""",
)
replace(
    "src/App.tsx",
    """  onMappingChange,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  onNext: () => void;\n}) {""",
    """  onMappingChange,\n  impactAnalysis,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  impactAnalysis?: MappingImpactResponse;\n  onNext: () => void;\n}) {""",
)
replace(
    "src/App.tsx",
    """      <p className=\"catalogStatus\">\n        {rows.filter((row) => row.include).length} of {rows.length} columnas incluidas""",
    """      {impactAnalysis && (\n        <section className={`mappingImpactPanel impact-${impactAnalysis.impact_level.toLowerCase()}`}>\n          <div className=\"sectionHeader\">\n            <div>\n              <span className=\"resultEyebrow\">Impact Analysis determinístico</span>\n              <h3>Impacto {impactAnalysis.impact_level} · Mapping v{impactAnalysis.proposed_mapping_version}</h3>\n            </div>\n            <span className=\"resultStatus\">{impactAnalysis.has_changes ? 'REQUIERE CONFIRMACIÓN' : 'SIN CAMBIOS'}</span>\n          </div>\n          <p>{impactAnalysis.summary}</p>\n          <div className=\"resultMetrics\">\n            <article><span>Agregadas</span><strong>{impactAnalysis.added_columns.length}</strong></article>\n            <article><span>Eliminadas</span><strong>{impactAnalysis.removed_columns.length}</strong></article>\n            <article><span>Modificadas</span><strong>{impactAnalysis.modified_columns.length}</strong></article>\n            <article><span>Reglas afectadas</span><strong>{impactAnalysis.affected_quality_rules.length}</strong></article>\n          </div>\n          {impactAnalysis.added_columns.length > 0 && <small>Agregadas: {impactAnalysis.added_columns.join(', ')}</small>}\n          {impactAnalysis.removed_columns.length > 0 && <small>Eliminadas: {impactAnalysis.removed_columns.join(', ')}</small>}\n          {impactAnalysis.modified_columns.length > 0 && <small>Modificadas: {impactAnalysis.modified_columns.join(', ')}</small>}\n          {impactAnalysis.affected_quality_rules.length > 0 && <small>Quality rules afectadas: {impactAnalysis.affected_quality_rules.join(', ')}</small>}\n          {impactAnalysis.downstream_invalidations.length > 0 && <small>Se regenerará/revalidará: {impactAnalysis.downstream_invalidations.join(' · ')}</small>}\n        </section>\n      )}\n      <p className=\"catalogStatus\">\n        {rows.filter((row) => row.include).length} of {rows.length} columnas incluidas""",
)
# The UI currently uses Spanish 'de', so support the real marker if the previous replacement did not fire.
app_path = ROOT / "src/App.tsx"
app_text = app_path.read_text()
if "mappingImpactPanel" not in app_text:
    old = """      <p className=\"catalogStatus\">\n        {rows.filter((row) => row.include).length} de {rows.length} columnas incluidas · Target:{' '}"""
    new = """      {impactAnalysis && (\n        <section className={`mappingImpactPanel impact-${impactAnalysis.impact_level.toLowerCase()}`}>\n          <div className=\"sectionHeader\">\n            <div>\n              <span className=\"resultEyebrow\">Impact Analysis determinístico</span>\n              <h3>Impacto {impactAnalysis.impact_level} · Mapping v{impactAnalysis.proposed_mapping_version}</h3>\n            </div>\n            <span className=\"resultStatus\">{impactAnalysis.has_changes ? 'REQUIERE CONFIRMACIÓN' : 'SIN CAMBIOS'}</span>\n          </div>\n          <p>{impactAnalysis.summary}</p>\n          <div className=\"resultMetrics\">\n            <article><span>Agregadas</span><strong>{impactAnalysis.added_columns.length}</strong></article>\n            <article><span>Eliminadas</span><strong>{impactAnalysis.removed_columns.length}</strong></article>\n            <article><span>Modificadas</span><strong>{impactAnalysis.modified_columns.length}</strong></article>\n            <article><span>Reglas afectadas</span><strong>{impactAnalysis.affected_quality_rules.length}</strong></article>\n          </div>\n          {impactAnalysis.added_columns.length > 0 && <small>Agregadas: {impactAnalysis.added_columns.join(', ')}</small>}\n          {impactAnalysis.removed_columns.length > 0 && <small>Eliminadas: {impactAnalysis.removed_columns.join(', ')}</small>}\n          {impactAnalysis.modified_columns.length > 0 && <small>Modificadas: {impactAnalysis.modified_columns.join(', ')}</small>}\n          {impactAnalysis.affected_quality_rules.length > 0 && <small>Quality rules afectadas: {impactAnalysis.affected_quality_rules.join(', ')}</small>}\n          {impactAnalysis.downstream_invalidations.length > 0 && <small>Se regenerará/revalidará: {impactAnalysis.downstream_invalidations.join(' · ')}</small>}\n        </section>\n      )}\n      <p className=\"catalogStatus\">\n        {rows.filter((row) => row.include).length} de {rows.length} columnas incluidas · Target:{' '}"""
    if old not in app_text:
        raise SystemExit("Pattern not found for mapping impact panel")
    app_path.write_text(app_text.replace(old, new, 1))

replace(
    "src/App.tsx",
    """      <button className=\"primary\" onClick={onNext}>Guardar mapping aprobado</button>""",
    """      <button className=\"primary\" onClick={onNext}>\n        {workflow.resumedFromBackend\n          ? impactAnalysis?.has_changes ? 'Confirmar impacto y crear nueva versión' : 'Analizar impacto del cambio'\n          : 'Guardar mapping aprobado'}\n      </button>""",
)

# 7) Minimal impact panel styles.
css_path = ROOT / "src/App.css"
if css_path.exists():
    with css_path.open("a") as css:
        css.write("\n.mappingImpactPanel{margin:16px 0;border:1px solid #d0d5dd;border-radius:14px;padding:16px;display:grid;gap:10px}.mappingImpactPanel small{display:block;color:#667085;overflow-wrap:anywhere}.mappingImpactPanel.impact-high{border-color:#fda29b}.mappingImpactPanel.impact-medium{border-color:#fec84b}.mappingImpactPanel.impact-low{border-color:#84caff}\n")

# 8) Focused backend unit test.
test_path = ROOT / "backend/deployable/silver-refinement-agent/tests/test_mapping_impact_analysis.py"
test_path.write_text('''from datetime import datetime, timezone\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, BusinessRule, BusinessRulesSection, BusinessRuleSeverity,\n    BusinessRuleStatus, BusinessRuleType, MappingImpactRequest, SchemaColumnEvidence,\n    SchemaContextEvidence, SilverMappingColumn, SilverTargetReference, SilverWorkflowRecord,\n    WorkflowStatus,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_mapping_impact_is_read_only_and_detects_downstream_effects():\n    now = datetime.now(timezone.utc)\n    repo = InMemoryWorkflowRepository()\n    record = SilverWorkflowRecord(\n        workflow_id=\"workflow_impact\", version=5, status=WorkflowStatus.SUCCEEDED, active_step=8,\n        source=BronzeSourceReference(connection_id=\"bq\", project_id=\"p\", dataset_id=\"bronze\", table_id=\"ventas\"),\n        source_confirmed=True,\n        schema_context=SchemaContextEvidence(columns=[\n            SchemaColumnEvidence(name=\"id\", data_type=\"INT64\", nullable=False),\n            SchemaColumnEvidence(name=\"monto\", data_type=\"NUMERIC\", nullable=True),\n        ]),\n        business_rules=BusinessRulesSection(status=BusinessRuleStatus.CONFIRMED, rules=[\n            BusinessRule(rule_id=\"r1\", name=\"id valido\", description=\"id requerido\",\n                rule_type=BusinessRuleType.VALIDATION, expression=\"id IS NOT NULL\",\n                severity=BusinessRuleSeverity.ERROR, source_columns=[\"id\"], target_columns=[\"id\"], rationale=\"clave\")\n        ]),\n        mapping_rules=[{\"name\": \"id\", \"data_type\": \"INT64\", \"nullable\": False, \"source_column\": \"id\", \"transformation\": \"DIRECT\"}],\n        mapping_version=2, silver_target=SilverTargetReference(project_id=\"p\", dataset_id=\"silver\", table_id=\"ventas\"),\n        quality_rules=[{\"rule_name\": \"id_not_null\", \"column_name\": \"id\"}],\n        spec_id=\"spec2\", execution_id=\"exec2\", correlation_id=\"corr\", created_by=\"tester\", created_at=now, updated_at=now,\n    )\n    repo.create(record)\n    service = SilverWorkflowService(repository=repo)\n\n    impact = service.analyze_mapping_impact(\"workflow_impact\", MappingImpactRequest(\n        expected_version=5,\n        target=SilverTargetReference(project_id=\"p\", dataset_id=\"silver\", table_id=\"ventas\"),\n        columns=[SilverMappingColumn(name=\"monto\", data_type=\"NUMERIC\", nullable=True, source_column=\"monto\", transformation=\"DIRECT\")],\n    ))\n\n    assert impact.has_changes is True\n    assert impact.proposed_mapping_version == 3\n    assert impact.added_columns == [\"monto\"]\n    assert impact.removed_columns == [\"id\"]\n    assert impact.affected_quality_rules == [\"id_not_null\"]\n    assert impact.impact_level == \"HIGH\"\n    assert \"ARTIFACT_PACKAGE\" in impact.downstream_invalidations\n    assert repo.get(\"workflow_impact\").version == 5\n''')

print("PASS: Impact Analysis gobernado de Mapping aplicado.")
print("Preview determinístico read-only + confirmación humana antes de crear nueva versión.")
