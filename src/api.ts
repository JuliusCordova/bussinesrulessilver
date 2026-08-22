import type { CatalogField, GeneratedArtifact, WorkflowState } from './types';

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

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
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
  return response.blob();
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

  listWorkflows: (limit = 50, status?: WorkflowState['status']) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (status) query.set('status', status);
    return request<SilverWorkflowListResponse>(`/silver-workflows?${query.toString()}`);
  },

  getWorkflow: (workflowId: string) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}`),

  listWorkflowVersions: (workflowId: string) =>
    request<SilverWorkflowVersionListResponse>(`/silver-workflows/${workflowId}/versions`),

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

  analyzeMappingImpact: (workflowId: string, payload: unknown) =>
    request<MappingImpactResponse>(`/silver-workflows/${workflowId}/mapping/impact`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  saveMapping: (workflowId: string, payload: unknown) =>
    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/mapping`, {
      method: 'PUT',
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

  listArtifacts: (specId: string) =>
    request<GeneratedArtifact[]>(`/silver-refinement/specs/${specId}/artifacts`),

  downloadArtifact: (specId: string, artifactType: string) =>
    requestBlob(
      `/silver-refinement/specs/${specId}/artifacts/current/${artifactType}/download`,
    ),

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

  generateTableProfileReport: (payload: SilverAgentRunRequest) =>
    requestBlob('/silver-agents/table-profiler/report', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getAgentOpsDashboard: () =>
    request<AgentOpsDashboard>('/agentops/dashboard'),

  getAgentOpsHealth: () =>
    request<AgentOpsHealth>('/agentops/health'),

  getAgentGovernanceSummary: () =>
    request<AgentGovernanceSummary>('/agentops/governance/summary'),

  getAgentGovernanceRuns: (limit = 50) =>
    request<AgentGovernanceRuns>(`/agentops/governance/runs?limit=${limit}`),

  getAgentOpsExecutions: (limit = 25) =>
    request<AgentOpsExecutions>(`/agentops/executions?limit=${limit}`),

  getAgentOpsAlerts: (limit = 25) =>
    request<AgentOpsAlerts>(`/agentops/alerts?limit=${limit}`),
};

export type SilverAgentName =
  | 'table-profiler'
  | 'mapping-advisor'
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
  requested_by?: string | null;
}

export interface SilverAgentRunResponse {
  agent_name: string;
  session_id: string;
  status: string;
  output: string;
  events: number;
  evidence?: Record<string, unknown> | null;
}

export interface SilverSourceReference {
  connection_id: string;
  project_id?: string | null;
  dataset_id: string;
  table_id: string;
  fully_qualified_name?: string | null;
}

export interface SilverTargetReference {
  project_id: string;
  dataset_id: string;
  table_id: string;
}

export interface SilverBusinessRulesSection {
  status?: string;
  proposal_id?: string | null;
  rules?: Array<Record<string, unknown>>;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  last_modified_by?: string | null;
  last_modified_at?: string | null;
}

export interface SilverWorkflowRecord {
  workflow_id: string;
  version: number;
  status: WorkflowState['status'];
  active_step: number;
  source: SilverSourceReference;
  source_confirmed?: boolean;
  schema_context?: Record<string, unknown> | null;
  business_rules?: SilverBusinessRulesSection;
  mapping_rules?: Array<Record<string, unknown>>;
  mapping_version?: number | null;
  silver_target?: SilverTargetReference | null;
  quality_rules?: Array<Record<string, unknown>>;
  quality_review?: Record<string, unknown> | null;
  artifact_package?: Record<string, unknown> | null;
  governance?: Record<string, unknown> | null;
  execution?: Record<string, unknown> | null;
  validation?: Record<string, unknown> | null;
  spec_id?: string | null;
  execution_id?: string | null;
  available_actions?: string[];
  correlation_id?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, unknown>;
}

export interface SilverWorkflowListResponse {
  total: number;
  workflows: SilverWorkflowRecord[];
}

export interface SilverWorkflowVersionSummary {
  workflow_id: string;
  workflow_version: number;
  mapping_version?: number | null;
  spec_id?: string | null;
  package_version?: number | null;
  execution_id?: string | null;
  status: WorkflowState['status'];
  updated_at: string;
  lifecycle_status: 'CURRENT' | 'SUPERSEDED' | string;
}

export interface SilverWorkflowVersionListResponse {
  workflow_id: string;
  current_version: number;
  total: number;
  versions: SilverWorkflowVersionSummary[];
}

export interface MappingImpactResponse {
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
  artifacts: GeneratedArtifact[];
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
  schema?: CatalogField[] | {
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
  partitioning?: string | null;
  clustering_columns?: string[];
}

export interface CatalogBackendField {
  name: string;
  type?: string;
  data_type?: string;
  mode?: string;
  description?: string;
}

export function demoWorkflowPatch(action: string): Partial<WorkflowState> {
  const now = new Date().toISOString().slice(11, 19);
  return { lastAction: `${action} · ${now}`, error: undefined };
}


export interface AgentOpsDashboard {
  generated_at: string;
  summary: {
    total_specs: number;
    total_executions: number;
    pending: number;
    validated: number;
    queued: number;
    running: number;
    succeeded: number;
    failed: number;
    cancelled: number;
    success_rate: number;
  };
  today: {
    executions: number;
    rows_read: number;
    rows_written: number;
    avg_runtime_seconds: number;
  };
  artifacts: {
    total_artifacts: number;
    current_packages: number;
    latest_package_version: number;
  };
  agents: Array<{ name: string; status: string; last_execution_at?: string | null }>;
}

export interface AgentOpsHealth {
  checked_at: string;
  overall_status: string;
  healthy_components: number;
  total_components: number;
  components: Array<{
    component: string;
    status: string;
    latency_ms: number;
    detail: string;
  }>;
}

export interface AgentGovernanceSummary {
  total_runs: number;
  active_agents: number;
  completed: number;
  failed: number;
  runs_today: number;
  avg_duration_ms: number;
  last_run_at?: string | null;
}

export interface AgentGovernanceRun {
  run_id: string;
  agent_name: string;
  session_id?: string | null;
  status: string;
  requested_by?: string | null;
  source_table?: string | null;
  target_table?: string | null;
  event_count: number;
  duration_ms: number;
  started_at: string;
  finished_at: string;
  error_message?: string | null;
}

export interface AgentGovernanceRuns {
  runs: AgentGovernanceRun[];
  total: number;
}

export interface AgentOpsExecutions {
  executions: Array<Record<string, unknown>>;
  total: number;
  limit: number;
  offset: number;
}

export interface AgentOpsAlerts {
  generated_at: string;
  total: number;
  unread: number;
  alerts: Array<Record<string, unknown>>;
}
