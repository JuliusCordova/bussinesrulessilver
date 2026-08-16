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
  | 'execution';

export interface WorkflowState {
  workflowId?: string;
  version?: number;
  specId?: string;
  mappingVersion?: number;
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
  agentProfile?: Record<string, unknown>;
  qualityRuleProposals?: Array<Record<string, unknown>>;
  approvedQualityRules?: Array<Record<string, unknown>>;
  agentSessionId?: string;
  lastAction?: string;
  error?: string;
  errorDetail?: string;
  processingLabel?: string;
  backendMessage?: string;
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
  sourceColumn?: string;
  targetColumn: string;
  targetType: string;
  transformationType: string;
  expression?: string;
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
