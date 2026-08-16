import type { CatalogField, WorkflowState } from './types';

const DEFAULT_BASE_URL = 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';

export const apiConfig = {
  baseUrl: import.meta.env.VITE_SILVER_API_URL ?? (import.meta.env.DEV ? '/api' : DEFAULT_BASE_URL),
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiConfig.baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Backend ${response.status}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

export const silverApi = {
  health: () => request<{ status: string; module: string; version: string }>('/health'),

  listDatasets: (projectId: string) =>
    request<CatalogDatasetResponse>(`/silver-workflows/catalog/projects/${projectId}/datasets`),

  listTables: (projectId: string, datasetId: string) =>
    request<CatalogTablesResponse>(
      `/silver-workflows/catalog/projects/${projectId}/datasets/${datasetId}/tables`,
    ),

  getTable: (projectId: string, datasetId: string, tableId: string) =>
    request<CatalogTableDetail>(
      `/silver-workflows/catalog/projects/${projectId}/datasets/${datasetId}/tables/${tableId}`,
    ),

  createWorkflow: (payload: unknown) =>
    request<SilverWorkflowRecord>('/silver-workflows', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getWorkflow: (workflowId: string) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}`),

  confirmSource: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/confirm-source`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generateMapping: (workflowId: string, payload: unknown) =>
    request<MappingRecommendationResponse>(`/silver-workflows/${workflowId}/mapping-recommendations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generateBusinessRules: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/business-rules/generate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  saveBusinessRulesDraft: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/business-rules/draft`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  confirmBusinessRules: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/business-rules/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reviewQuality: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/quality-review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  saveSpecification: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/specification`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generateArtifacts: (specId: string, payload: unknown) =>
    request<ArtifactPackageResponse>(`/silver-refinement/specs/${specId}/artifacts/generate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createExecution: (payload: unknown) =>
    request<ExecutionRecord>('/executions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  validatePackage: (executionId: string) =>
    request<PackageValidationResponse>(`/executions/${executionId}/validate-package`, {
      method: 'POST',
    }),

  submitDataproc: (executionId: string) =>
    request<DataprocSubmissionResponse>(`/executions/${executionId}/submit`, {
      method: 'POST',
    }),

  syncExecution: (executionId: string) =>
    request<ExecutionMonitoringResponse>(`/executions/${executionId}/sync-status`, {
      method: 'POST',
    }),

  getExecutionResult: (executionId: string) =>
    request<BigQueryValidationResponse>(`/executions/${executionId}/result`, {
      method: 'POST',
    }),

  listSilverAgents: () =>
    request<SilverAgentDescriptor[]>('/silver-agents'),

  runSilverAgent: (agentName: SilverAgentName, payload: SilverAgentRunRequest) =>
    request<SilverAgentRunResponse>(`/silver-agents/${agentName}/run`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export type SilverAgentName =
  | 'table-profiler'
  | 'quality-rule-advisor'
  | 'business-rule-validator'
  | 'notebook-generator'
  | 'orchestrator';

export interface SilverAgentDescriptor {
  name: SilverAgentName;
  purpose: string;
  model: string;
  deterministic_tools: string[];
}

export interface SilverAgentRunRequest {
  project_id: string;
  source_dataset: string;
  source_table: string;
  target_project_id?: string | null;
  target_dataset: string;
  target_table: string;
  columns: Array<Record<string, unknown>>;
  load_strategy: Record<string, unknown>;
  physical_design?: Record<string, unknown>;
  business_keys: string[];
  watermark_column?: string | null;
  business_rules?: Array<Record<string, unknown>>;
  approved_quality_rules?: Array<Record<string, unknown>>;
  context?: string | null;
}

export interface SilverAgentRunResponse {
  agent_name: string;
  session_id: string;
  status: string;
  output: string;
  events: number;
  evidence?: Record<string, unknown> | null;
}

export interface SilverWorkflowRecord {
  workflow_id: string;
  version: number;
  status: WorkflowState['status'];
  active_step: number;
  spec_id?: string | null;
  execution_id?: string | null;
  mapping_version?: number | null;
  available_actions?: string[];
  business_rules?: { proposal_id?: string | null; rules?: unknown[] };
  mapping_rules?: unknown[];
  silver_target?: unknown;
}

export interface MappingRecommendationResponse {
  workflow_id: string;
  source_workflow_version: number;
  target_project: string;
  target_dataset: string;
  target_table: string;
  columns: Array<Record<string, unknown>>;
  load_strategy: Record<string, unknown>;
  physical_design: Record<string, unknown>;
}

export interface ArtifactPackageResponse {
  spec_id: string;
  mapping_version: number;
  artifacts: Array<Record<string, unknown>>;
}

export interface ExecutionRecord {
  execution_id: string;
  spec_id: string;
  mapping_version: number;
  package_version: number;
  artifact_package_uri: string;
  status?: string;
  error_message?: string | null;
}

export interface PackageValidationResponse {
  execution: ExecutionRecord;
  current_uri: string;
  manifest_uri: string;
  package_hash: string;
  files_validated: number;
}

export interface DataprocSubmissionResponse {
  execution: ExecutionRecord;
  batch_id: string;
  batch_name: string;
  pyspark_uri: string;
  operation_name?: string | null;
}

export interface BigQueryValidationCheck {
  name: string;
  status: 'PASS' | 'FAIL' | 'SKIPPED' | string;
  expected?: number | string | null;
  actual?: number | string | null;
  details?: string | null;
}

export interface BigQueryValidationResponse {
  execution: ExecutionRecord;
  status: string;
  conformant: boolean;
  source_table?: string | null;
  target_table: string;
  business_keys: string[];
  metric_column?: string | null;
  row_count: number;
  distinct_business_key_count?: number | null;
  duplicate_count: number;
  diff_count?: number | null;
  metric_sum?: number | null;
  checks: BigQueryValidationCheck[];
  validated_at: string;
}

export interface ExecutionMonitoringResponse {
  execution: ExecutionRecord;
  dataproc_state: string;
  state_message?: string | null;
  validation_result?: BigQueryValidationResponse | null;
}

export interface CatalogDatasetResponse {
  datasets?: Array<string | { dataset_id?: string; datasetId?: string; id?: string; name?: string }>;
  items?: Array<string | { dataset_id?: string; datasetId?: string; id?: string; name?: string }>;
}

export interface CatalogTablesResponse {
  tables?: Array<string | { table_id?: string; tableId?: string; id?: string; name?: string }>;
  items?: Array<string | { table_id?: string; tableId?: string; id?: string; name?: string }>;
}

export interface CatalogTableDetail {
  schema?: {
    fields?: CatalogField[];
  };
  fields?: CatalogField[];
  columns?: CatalogField[];
  table?: {
    schema?: {
      fields?: CatalogField[];
    };
    fields?: CatalogField[];
    columns?: CatalogField[];
  };
  row_count?: number;
  numRows?: number;
}

export function demoWorkflowPatch(action: string): Partial<WorkflowState> {
  const now = new Date().toISOString().slice(11, 19);
  return { lastAction: `${action} · ${now}`, error: undefined };
}
