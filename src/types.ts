export type WorkflowStatus =
  | 'DRAFT'
  | 'IN_PROGRESS'
  | 'AWAITING_REVIEW'
  | 'APPROVED'
  | 'EXECUTING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED';

export type ExecutionStatus =
  | 'PENDING'
  | 'VALIDATED'
  | 'QUEUED'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED';

export type StepId =
  | 'source'
  | 'incremental'
  | 'mapping'
  | 'rules'
  | 'artifacts'
  | 'execution'
  | 'governance';

export interface WorkflowState {
  workflowId?: string;
  version?: number;
  specId?: string;
  mappingVersion?: number;
  packageVersion?: number;
  executionId?: string;
  batchId?: string;
  stateMessage?: string;
  status: WorkflowStatus;
  executionStatus?: ExecutionStatus;
  activeStep: StepId;
  projectId?: string;
  sourceDataset?: string;
  sourceTable?: string;
  targetDataset?: string;
  targetTable?: string;
  sourceColumns?: CatalogField[];
  businessKeys?: string[];
  watermarkColumn?: string;
  metricColumn?: string;
  loadStrategy?: 'FULL' | 'MERGE';
  inferenceSource?: 'SCHEMA' | 'BIGQUERY_PROFILE' | 'USER';
  inferenceReasons?: string[];
  profileReportUrl?: string;
  mappingRules?: MappingRule[];
  mappingSource?: 'DIRECT' | 'DETERMINISTIC' | 'AGENT' | 'USER';
  agentProfile?: Record<string, unknown>;
  qualityRuleProposals?: Array<Record<string, unknown>>;
  approvedQualityRules?: Array<Record<string, unknown>>;
  qualityReviewed?: boolean;
  qualityReviewDecision?: string;
  generatedArtifacts?: GeneratedArtifact[];
  agentSessionId?: string;
  lastAction?: string;
  error?: string;
  errorDetail?: string;
  processingLabel?: string;
  backendMessage?: string;
  resumedFromBackend?: boolean;
  validationResult?: {
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
    checks: Array<{
      name: string;
      status: string;
      expected?: number | string | null;
      actual?: number | string | null;
      details?: string | null;
    }>;
    validated_at: string;
  };
}

export interface SeedColumn {
  name: string;
  type: string;
  usage: 'business_key' | 'watermark' | 'metric' | 'traceability' | 'dimension' | 'rule';
}

export interface MappingRule {
  sourceColumn: string;
  targetColumn: string;
  targetType: string;
  transformationType: string;
  include: boolean;
  nullable: boolean;
  parameters?: Record<string, unknown>;
  confidence?: number;
  reason?: string;
  risk?: string;
  requiresApproval?: boolean;
}

export interface BusinessRule {
  name: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  expression: string;
}

export interface CatalogField {
  name: string;
  type: string;
  mode?: string;
  description?: string;
}


export interface GeneratedArtifact {
  artifact_id?: string;
  artifact_type: string;
  artifact_name: string;
  artifact_version?: number;
  generation_status?: string;
  validation_status?: string;
  storage_uri?: string | null;
  content_hash?: string | null;
  is_current?: boolean;
  metadata?: Record<string, unknown>;
}
