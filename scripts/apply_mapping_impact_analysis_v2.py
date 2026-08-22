from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text)


def ensure_replace(path: str, old: str, new: str, *, already: str | None = None) -> None:
    text = read(path)
    if already and already in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:140]!r}")
    write(path, text.replace(old, new, 1))


# 1) Backend contract.
ensure_replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py",
    "class SaveSilverMappingRequest(BaseModel):",
    '''class MappingImpactRequest(BaseModel):
    expected_version: int = Field(ge=1)
    target: SilverTargetReference
    columns: list[SilverMappingColumn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_target_columns(self) -> "MappingImpactRequest":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Cada columna destino Silver debe tener un nombre único")
        return self


class MappingImpactResponse(BaseModel):
    workflow_id: str
    current_workflow_version: int = Field(ge=1)
    current_mapping_version: int | None = Field(default=None, ge=1)
    proposed_mapping_version: int = Field(ge=1)
    impact_level: str
    has_changes: bool
    added_columns: list[str] = Field(default_factory=list)
    removed_columns: list[str] = Field(default_factory=list)
    modified_columns: list[str] = Field(default_factory=list)
    affected_quality_rules: list[str] = Field(default_factory=list)
    downstream_invalidations: list[str] = Field(default_factory=list)
    summary: str


class SaveSilverMappingRequest(BaseModel):''',
    already="class MappingImpactRequest(BaseModel):",
)

# 2) Service imports.
ensure_replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    "    GenerateBusinessRulesRequest,\n    ReviewQualityRequest,",
    "    GenerateBusinessRulesRequest,\n    MappingImpactRequest,\n    MappingImpactResponse,\n    ReviewQualityRequest,",
    already="    MappingImpactRequest,",
)

# 3) Deterministic, read-only analyzer.
service_marker = "    def save_mapping_version(self, workflow_id: str, request: SaveSilverMappingRequest) -> SilverWorkflowRecord:\n"
analyzer = '''    @staticmethod
    def _mapping_shape(raw: dict[str, object]) -> dict[str, object]:
        return {
            "name": raw.get("name") or raw.get("target_column"),
            "data_type": raw.get("data_type") or raw.get("target_type"),
            "nullable": raw.get("nullable", True),
            "source_column": raw.get("source_column") or raw.get("sourceColumn"),
            "transformation": raw.get("transformation") or raw.get("transformation_type") or raw.get("transformationType"),
        }

    @staticmethod
    def _quality_rule_columns(rule: dict[str, object]) -> set[str]:
        columns: set[str] = set()
        for key in ("column_name", "column", "columns", "source_columns", "target_columns"):
            value = rule.get(key)
            if isinstance(value, str) and value:
                columns.add(value)
            elif isinstance(value, list):
                columns.update(str(item) for item in value if item)
        return columns

    def analyze_mapping_impact(self, workflow_id: str, request: MappingImpactRequest) -> MappingImpactResponse:
        current = self._require_version(workflow_id, request.expected_version)
        if not current.source_confirmed or current.schema_context is None:
            raise WorkflowStateConflictError("La fuente y el esquema deben estar confirmados antes de analizar el mapping")

        previous: dict[str, dict[str, object]] = {}
        for raw in current.mapping_rules:
            shape = self._mapping_shape(raw)
            if shape.get("name"):
                previous[str(shape["name"])] = shape
        proposed = {
            column.name: self._mapping_shape(column.model_dump(mode="json"))
            for column in request.columns
        }

        added = sorted(set(proposed) - set(previous))
        removed = sorted(set(previous) - set(proposed))
        modified = sorted(
            name for name in set(previous) & set(proposed)
            if previous[name] != proposed[name]
        )
        changed_columns = set(added) | set(removed) | set(modified)

        affected_rules: list[str] = []
        for rule in current.quality_rules:
            if isinstance(rule, dict) and self._quality_rule_columns(rule) & changed_columns:
                affected_rules.append(str(rule.get("rule_name") or rule.get("name") or "regla_sin_nombre"))

        has_changes = bool(changed_columns)
        invalidations = [
            "SPECIFICATION", "QUALITY_REVIEW", "ARTIFACT_PACKAGE",
            "GOVERNANCE", "EXECUTION", "VALIDATION",
        ] if has_changes else []
        if removed or affected_rules:
            impact_level = "HIGH"
        elif modified:
            impact_level = "MEDIUM"
        elif added:
            impact_level = "LOW"
        else:
            impact_level = "NONE"

        summary = (
            f"{len(added)} agregadas, {len(removed)} eliminadas, {len(modified)} modificadas; "
            f"{len(affected_rules)} reglas de calidad afectadas."
            if has_changes else "No se detectaron cambios materiales frente al mapping persistido."
        )
        return MappingImpactResponse(
            workflow_id=workflow_id,
            current_workflow_version=current.version,
            current_mapping_version=current.mapping_version,
            proposed_mapping_version=(current.mapping_version or 0) + 1,
            impact_level=impact_level,
            has_changes=has_changes,
            added_columns=added,
            removed_columns=removed,
            modified_columns=modified,
            affected_quality_rules=sorted(set(affected_rules)),
            downstream_invalidations=invalidations,
            summary=summary,
        )

'''
text = read("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py")
if "def analyze_mapping_impact(" not in text:
    if service_marker not in text:
        raise SystemExit("save_mapping_version marker not found in service.py")
    write("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py", text.replace(service_marker, analyzer + service_marker, 1))

# 4) Router imports and endpoint.
ensure_replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    "    GenerateBusinessRulesRequest,\n    ReviewQualityRequest,",
    "    GenerateBusinessRulesRequest,\n    MappingImpactRequest,\n    MappingImpactResponse,\n    ReviewQualityRequest,",
    already="    MappingImpactRequest,",
)
router_marker = '@router.put("/{workflow_id}/mapping", response_model=SilverWorkflowRecord)\n'
router_endpoint = '''@router.post("/{workflow_id}/mapping/impact", response_model=MappingImpactResponse)
def analyze_workflow_mapping_impact(workflow_id: str, request: MappingImpactRequest, business: WorkflowBusinessOperation = Depends(require_workflow_mapping)) -> MappingImpactResponse:
    try:
        result = business.workflow_service.analyze_mapping_impact(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return result
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


'''
text = read("backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py")
if '"/{workflow_id}/mapping/impact"' not in text:
    if router_marker not in text:
        raise SystemExit("mapping router marker not found")
    write("backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py", text.replace(router_marker, router_endpoint + router_marker, 1))

# 5) Frontend API.
ensure_replace(
    "src/api.ts",
    "  saveMapping: (workflowId: string, payload: unknown) =>\n",
    "  analyzeMappingImpact: (workflowId: string, payload: unknown) =>\n    request<MappingImpactResponse>(`/silver-workflows/${workflowId}/mapping/impact`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n  saveMapping: (workflowId: string, payload: unknown) =>\n",
    already="  analyzeMappingImpact:",
)
ensure_replace(
    "src/api.ts",
    "export interface MappingRecommendationResponse {",
    '''export interface MappingImpactResponse {
  workflow_id: string;
  current_workflow_version: number;
  current_mapping_version?: number | null;
  proposed_mapping_version: number;
  impact_level: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | string;
  has_changes: boolean;
  added_columns: string[];
  removed_columns: string[];
  modified_columns: string[];
  affected_quality_rules: string[];
  downstream_invalidations: string[];
  summary: string;
}

export interface MappingRecommendationResponse {''',
    already="export interface MappingImpactResponse {",
)

# 6) App import and state.
ensure_replace(
    "src/App.tsx",
    "  type CatalogTableDetail,\n  type SilverAgentDescriptor,",
    "  type CatalogTableDetail,\n  type MappingImpactResponse,\n  type SilverAgentDescriptor,",
    already="  type MappingImpactResponse,",
)
ensure_replace(
    "src/App.tsx",
    "  const [showDataprocConfirm, setShowDataprocConfirm] = useState(false);",
    "  const [showDataprocConfirm, setShowDataprocConfirm] = useState(false);\n  const [mappingImpact, setMappingImpact] = useState<MappingImpactResponse>();\n  const [mappingImpactFingerprint, setMappingImpactFingerprint] = useState<string>();",
    already="const [mappingImpact, setMappingImpact]",
)

# Remove any accidental impactAnalysis prop from IncrementalStep left by the failed v1 patch.
app = read("src/App.tsx")
app = app.replace("            impactAnalysis={mappingImpact}\n            onNext={async () => {\n              await runAction('Confirmando origen y estrategia incremental...'", "            onNext={async () => {\n              await runAction('Confirmando origen y estrategia incremental...'", 1)
write("src/App.tsx", app)

# Reset impact when mapping is edited.
ensure_replace(
    "src/App.tsx",
    "            onMappingChange={(rules) => {\n              setWorkflow((current) => ({",
    "            onMappingChange={(rules) => {\n              setMappingImpact(undefined);\n              setMappingImpactFingerprint(undefined);\n              setWorkflow((current) => ({",
    already="              setMappingImpact(undefined);\n              setMappingImpactFingerprint(undefined);",
)

# Add prop to the actual MappingStep invocation only.
ensure_replace(
    "src/App.tsx",
    "            onMappingChange={(rules) => {\n              setMappingImpact(undefined);\n              setMappingImpactFingerprint(undefined);",
    "            impactAnalysis={mappingImpact}\n            onMappingChange={(rules) => {\n              setMappingImpact(undefined);\n              setMappingImpactFingerprint(undefined);",
    already="            impactAnalysis={mappingImpact}\n            onMappingChange={(rules) => {",
)

old_resumed = '''              if (workflow.resumedFromBackend && workflow.workflowId) {
                await runAction('Persistiendo nueva versión gobernada del mapping...', async () => {
                  const includedRules = rules.filter((rule) => rule.include);
                  const updated = await silverApi.saveMapping(workflow.workflowId!, {
                    expected_version: currentVersion(workflow),
                    target: {
                      project_id: workflow.projectId ?? seedSource.projectId,
                      dataset_id: workflow.targetDataset ?? seedSource.targetDataset,
                      table_id: workflow.targetTable ?? seedSource.targetTable,
                    },
                    columns: includedRules.map((rule) => ({
                      name: rule.targetColumn,
                      data_type: rule.targetType,
                      nullable: rule.nullable,
                      source_column: rule.sourceColumn || null,
                      transformation: toBackendTransformation(rule.transformationType),
                    })),
                    edited_by: REQUESTED_BY,
                    change_reason: 'Mapping editado desde Procesos Silver; downstream requiere revalidación.',
                  });
                  setWorkflow((current) => ({
                    ...current,
                    ...workflowPatchFromRecord(updated),
                    mappingRules: rules,
                    mappingSource: 'USER',
                    mappingVersion: updated.mapping_version ?? current.mappingVersion,
                    specId: undefined,
                    executionId: undefined,
                    executionStatus: undefined,
                    generatedArtifacts: undefined,
                    qualityReviewed: false,
                    qualityReviewDecision: undefined,
                    activeStep: 'artifacts',
                    resumedFromBackend: true,
                    ...demoWorkflowPatch(`Mapping v${updated.mapping_version ?? '?'} persistido; Spec y Package requieren regeneración`),
                    backendMessage: JSON.stringify(updated),
                  }));
                });
                return;
              }
'''
new_resumed = '''              if (workflow.resumedFromBackend && workflow.workflowId) {
                const includedRules = rules.filter((rule) => rule.include);
                const payload = {
                  expected_version: currentVersion(workflow),
                  target: {
                    project_id: workflow.projectId ?? seedSource.projectId,
                    dataset_id: workflow.targetDataset ?? seedSource.targetDataset,
                    table_id: workflow.targetTable ?? seedSource.targetTable,
                  },
                  columns: includedRules.map((rule) => ({
                    name: rule.targetColumn,
                    data_type: rule.targetType,
                    nullable: rule.nullable,
                    source_column: rule.sourceColumn || null,
                    transformation: toBackendTransformation(rule.transformationType),
                  })),
                };
                const fingerprint = JSON.stringify(payload);
                if (!mappingImpact || mappingImpactFingerprint !== fingerprint) {
                  await runAction('Analizando impacto del cambio de mapping...', async () => {
                    const impact = await silverApi.analyzeMappingImpact(workflow.workflowId!, payload);
                    setMappingImpact(impact);
                    setMappingImpactFingerprint(fingerprint);
                  });
                  return;
                }
                if (!mappingImpact.has_changes) {
                  applyError(new Error('No se detectaron cambios materiales frente al mapping persistido.'));
                  return;
                }
                await runAction('Persistiendo nueva versión gobernada del mapping...', async () => {
                  const updated = await silverApi.saveMapping(workflow.workflowId!, {
                    ...payload,
                    edited_by: REQUESTED_BY,
                    change_reason: `Impact Analysis ${mappingImpact.impact_level}: ${mappingImpact.summary}`,
                  });
                  setMappingImpact(undefined);
                  setMappingImpactFingerprint(undefined);
                  setWorkflow((current) => ({
                    ...current,
                    ...workflowPatchFromRecord(updated),
                    mappingRules: rules,
                    mappingSource: 'USER',
                    mappingVersion: updated.mapping_version ?? current.mappingVersion,
                    specId: undefined,
                    executionId: undefined,
                    executionStatus: undefined,
                    generatedArtifacts: undefined,
                    qualityReviewed: false,
                    qualityReviewDecision: undefined,
                    activeStep: 'artifacts',
                    resumedFromBackend: true,
                    ...demoWorkflowPatch(`Mapping v${updated.mapping_version ?? '?'} persistido; Spec y Package requieren regeneración`),
                    backendMessage: JSON.stringify(updated),
                  }));
                });
                return;
              }
'''
text = read("src/App.tsx")
if "Analizando impacto del cambio de mapping..." not in text:
    if old_resumed not in text:
        raise SystemExit("resumed mapping save block not found in App.tsx")
    write("src/App.tsx", text.replace(old_resumed, new_resumed, 1))

# MappingStep prop contract.
ensure_replace(
    "src/App.tsx",
    "  onMappingChange,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  onNext: () => void;\n}) {",
    "  onMappingChange,\n  impactAnalysis,\n  onNext,\n}: {\n  workflow: WorkflowState;\n  onGenerateDeterministic: () => void;\n  onGenerateAgent: () => void;\n  onMappingChange: (rules: MappingRule[]) => void;\n  impactAnalysis?: MappingImpactResponse;\n  onNext: () => void;\n}) {",
    already="  impactAnalysis?: MappingImpactResponse;",
)

# Visible analysis gate.
impact_panel = '''      {impactAnalysis && (
        <div className="validationBox">
          <strong>Impact Analysis · {impactAnalysis.impact_level}</strong>
          <span>{impactAnalysis.summary}</span>
          <small>Agregadas: {impactAnalysis.added_columns.join(', ') || 'Ninguna'}</small>
          <small>Eliminadas: {impactAnalysis.removed_columns.join(', ') || 'Ninguna'}</small>
          <small>Modificadas: {impactAnalysis.modified_columns.join(', ') || 'Ninguna'}</small>
          <small>Reglas afectadas: {impactAnalysis.affected_quality_rules.join(', ') || 'Ninguna'}</small>
          <small>Se regenerará: {impactAnalysis.downstream_invalidations.join(', ') || 'Nada'}</small>
        </div>
      )}
'''
text = read("src/App.tsx")
if "Impact Analysis · {impactAnalysis.impact_level}" not in text:
    marker = '''      <div className="actions">
        <button onClick={addRow}>Agregar mapping</button>
      </div>
'''
    if marker not in text:
        raise SystemExit("mapping actions marker not found in App.tsx")
    write("src/App.tsx", text.replace(marker, impact_panel + marker, 1))

# Button copy makes the two-step gate explicit.
text = read("src/App.tsx")
old_button = '<button className="primary" onClick={onNext}>Guardar mapping aprobado</button>'
new_button = '<button className="primary" onClick={onNext}>{impactAnalysis?.has_changes ? `Confirmar nueva versión v${impactAnalysis.proposed_mapping_version}` : workflow.resumedFromBackend ? \'Analizar impacto\' : \'Guardar mapping aprobado\'}</button>'
if old_button in text:
    write("src/App.tsx", text.replace(old_button, new_button, 1))

# 7) Focused test: impact is deterministic and does not mutate current version.
test = ROOT / "backend/deployable/silver-refinement-agent/tests/test_mapping_impact_analysis.py"
test.write_text('''from datetime import datetime, timezone\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, MappingImpactRequest, SchemaColumnEvidence, SchemaContextEvidence,\n    SilverMappingColumn, SilverTargetReference, SilverWorkflowRecord, WorkflowStatus,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_mapping_impact_is_read_only_and_marks_downstream_invalidation():\n    now = datetime.now(timezone.utc)\n    repo = InMemoryWorkflowRepository()\n    record = SilverWorkflowRecord(\n        workflow_id="workflow_impact", version=7, status=WorkflowStatus.SUCCEEDED, active_step=8,\n        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),\n        source_confirmed=True,\n        schema_context=SchemaContextEvidence(columns=[\n            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),\n            SchemaColumnEvidence(name="monto", data_type="NUMERIC", nullable=True),\n        ]),\n        mapping_rules=[{\"name\": \"id\", \"data_type\": \"INT64\", \"nullable\": False, \"source_column\": \"id\", \"transformation\": \"DIRECT\"}],\n        mapping_version=3, silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),\n        quality_rules=[{\"rule_name\": \"id_not_null\", \"column_name\": \"id\"}],\n        spec_id="spec_old", execution_id="exec_old", correlation_id="corr", created_by="tester",\n        created_at=now, updated_at=now,\n    )\n    repo.create(record)\n    service = SilverWorkflowService(repository=repo)\n\n    impact = service.analyze_mapping_impact("workflow_impact", MappingImpactRequest(\n        expected_version=7,\n        target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),\n        columns=[\n            SilverMappingColumn(name="id", data_type="INT64", nullable=False, source_column="id", transformation="DIRECT"),\n            SilverMappingColumn(name="monto", data_type="NUMERIC", nullable=True, source_column="monto", transformation="DIRECT"),\n        ],\n    ))\n\n    assert impact.has_changes is True\n    assert impact.added_columns == ["monto"]\n    assert impact.proposed_mapping_version == 4\n    assert "SPECIFICATION" in impact.downstream_invalidations\n    assert repo.get("workflow_impact").version == 7\n''')

print("PASS: Impact Analysis gobernado de Mapping v2 aplicado desde baseline limpio.")
print("Preview read-only + gate humano + persistencia solo tras confirmación explícita.")
