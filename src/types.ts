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
  specId?: string;
  executionId?: string;
  status: WorkflowStatus;
  executionStatus?: ExecutionStatus;
  activeStep: StepId;
  lastAction?: string;
  error?: string;
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

