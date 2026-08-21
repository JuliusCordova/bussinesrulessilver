import type { SilverWorkflowRecord } from './api';
import type { CatalogField, MappingRule, StepId, WorkflowState } from './types';

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function schemaColumns(workflow: SilverWorkflowRecord): CatalogField[] {
  const context = asRecord(workflow.schema_context);
  const rawColumns = Array.isArray(context?.columns) ? context.columns : [];
  const columns: CatalogField[] = [];

  for (const raw of rawColumns) {
    const column = asRecord(raw);
    if (!column) continue;

    const name = String(column.name ?? '');
    const type = String(column.data_type ?? column.type ?? '');
    if (!name || !type) continue;

    columns.push({
      name,
      type,
      mode: column.nullable === false ? 'REQUIRED' : String(column.mode ?? 'NULLABLE'),
      description: typeof column.description === 'string' ? column.description : undefined,
    });
  }

  return columns;
}

function mappingRules(workflow: SilverWorkflowRecord): MappingRule[] {
  const rules: MappingRule[] = [];

  for (const raw of workflow.mapping_rules ?? []) {
    const row = asRecord(raw);
    if (!row) continue;

    const transformation = asRecord(row.transformation);
    const sourceColumns = Array.isArray(transformation?.source_columns)
      ? transformation.source_columns.map(String)
      : [];
    const sourceColumn = String(
      row.source_column ?? sourceColumns[0] ?? row.name ?? '',
    );
    const targetColumn = String(row.target_column ?? row.name ?? '');
    const targetType = String(row.target_type ?? row.data_type ?? 'STRING');
    if (!targetColumn) continue;

    rules.push({
      sourceColumn,
      targetColumn,
      targetType,
      transformationType: String(
        transformation?.type ?? row.transformation_type ?? (sourceColumn ? 'DIRECT' : 'DERIVED'),
      ),
      include: row.include !== false,
      nullable: row.nullable !== false,
      parameters: asRecord(transformation?.parameters) ?? asRecord(row.parameters) ?? {},
      confidence: typeof row.confidence === 'number' ? row.confidence : undefined,
      reason:
        typeof row.reason === 'string'
          ? row.reason
          : typeof row.recommendation_reason === 'string'
            ? row.recommendation_reason
            : 'Mapping recuperado del workflow persistido.',
      risk:
        typeof row.risk === 'string'
          ? row.risk
          : typeof row.recommendation_risk === 'string'
            ? row.recommendation_risk
            : undefined,
      requiresApproval: Boolean(row.requires_approval),
    });
  }

  return rules;
}

function inferKeys(workflow: SilverWorkflowRecord): string[] {
  const context = asRecord(workflow.schema_context);
  const metadata = asRecord(context?.metadata);
  const candidates =
    (Array.isArray(context?.business_key_candidates) && context.business_key_candidates) ||
    (Array.isArray(metadata?.business_key_candidates) && metadata.business_key_candidates) ||
    [];
  return candidates.map(String).filter(Boolean).slice(0, 4);
}

function inferWatermark(workflow: SilverWorkflowRecord) {
  const context = asRecord(workflow.schema_context);
  const metadata = asRecord(context?.metadata);
  const candidates =
    (Array.isArray(context?.watermark_candidates) && context.watermark_candidates) ||
    (Array.isArray(metadata?.watermark_candidates) && metadata.watermark_candidates) ||
    [];
  return candidates.length ? String(candidates[0]) : undefined;
}

function inferMetric(workflow: SilverWorkflowRecord) {
  const context = asRecord(workflow.schema_context);
  const metadata = asRecord(context?.metadata);
  const candidates =
    (Array.isArray(context?.metric_candidates) && context.metric_candidates) ||
    (Array.isArray(metadata?.metric_candidates) && metadata.metric_candidates) ||
    [];
  return candidates.length ? String(candidates[0]) : undefined;
}

function executionStatus(workflow: SilverWorkflowRecord): WorkflowState['executionStatus'] | undefined {
  const execution = asRecord(workflow.execution);
  const raw = execution?.status;
  if (typeof raw !== 'string') return undefined;
  const normalized = raw.toUpperCase();
  return ['PENDING', 'VALIDATED', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(normalized)
    ? normalized as WorkflowState['executionStatus']
    : undefined;
}

function resumeStep(workflow: SilverWorkflowRecord): StepId {
  if (workflow.execution_id || workflow.execution) return 'execution';
  if (workflow.artifact_package || workflow.spec_id || workflow.quality_review) return 'artifacts';
  if ((workflow.quality_rules?.length ?? 0) > 0 || (workflow.business_rules?.rules?.length ?? 0) > 0) {
    return 'rules';
  }
  if ((workflow.mapping_rules?.length ?? 0) > 0 || workflow.mapping_version) return 'mapping';
  if (workflow.source_confirmed) return 'incremental';
  return 'source';
}

export function hydrateWorkflowForResume(workflow: SilverWorkflowRecord): WorkflowState {
  const columns = schemaColumns(workflow);
  const keys = inferKeys(workflow);
  const target = workflow.silver_target;
  const qualityReview = asRecord(workflow.quality_review);
  const validation = asRecord(workflow.validation);

  return {
    workflowId: workflow.workflow_id,
    version: workflow.version,
    status: workflow.status,
    activeStep: resumeStep(workflow),
    specId: workflow.spec_id ?? undefined,
    mappingVersion: workflow.mapping_version ?? undefined,
    packageVersion: (() => {
      const pkg = asRecord(workflow.artifact_package);
      const execution = asRecord(workflow.execution);
      const value = pkg?.package_version ?? execution?.package_version;
      return typeof value === 'number' ? value : undefined;
    })(),
    executionId: workflow.execution_id ?? undefined,
    executionStatus: executionStatus(workflow),
    projectId: workflow.source?.project_id ?? target?.project_id ?? undefined,
    sourceDataset: workflow.source?.dataset_id,
    sourceTable: workflow.source?.table_id,
    targetDataset: target?.dataset_id,
    targetTable: target?.table_id,
    sourceColumns: columns,
    businessKeys: keys,
    watermarkColumn: inferWatermark(workflow),
    metricColumn: inferMetric(workflow),
    loadStrategy: keys.length ? 'MERGE' : 'FULL',
    inferenceSource: 'SCHEMA',
    inferenceReasons: [
      `Proceso recuperado desde backend · workflow ${workflow.workflow_id} v${workflow.version}.`,
    ],
    mappingRules: mappingRules(workflow),
    mappingSource: (workflow.mapping_rules?.length ?? 0) > 0 ? 'USER' : undefined,
    approvedQualityRules: workflow.quality_rules ?? [],
    qualityReviewed: Boolean(workflow.quality_review),
    qualityReviewDecision:
      typeof qualityReview?.decision === 'string' ? qualityReview.decision : undefined,
    validationResult:
      validation && typeof validation.status === 'string' && typeof validation.conformant === 'boolean'
        ? validation as NonNullable<WorkflowState['validationResult']>
        : undefined,
    lastAction: `Proceso persistido recuperado · v${workflow.version}`,
    resumedFromBackend: true,
    backendMessage: JSON.stringify({
      workflow_id: workflow.workflow_id,
      version: workflow.version,
      status: workflow.status,
      mapping_version: workflow.mapping_version,
      spec_id: workflow.spec_id,
      execution_id: workflow.execution_id,
    }),
  };
}
