export type BackendTransformationType =
  | 'DIRECT'
  | 'TRIM'
  | 'COALESCE'
  | 'CAST'
  | 'UPPER'
  | 'LOWER'
  | 'CONCAT'
  | 'DATE_PARSE'
  | 'EXCLUDE';

export interface BackendTransformation {
  type: BackendTransformationType;
  expression?: string;
  parameters?: Record<string, unknown>;
}

const transformationAliases: Record<string, BackendTransformationType> = {
  DIRECT: 'DIRECT',
  DIRECT_COPY: 'DIRECT',
  COPY: 'DIRECT',
  TRACE_COPY: 'DIRECT',
  TRIM: 'TRIM',
  TRIM_TEXT: 'TRIM',
  COALESCE: 'COALESCE',
  CAST: 'CAST',
  UPPER: 'UPPER',
  UPPER_TEXT: 'UPPER',
  LOWER: 'LOWER',
  LOWER_TEXT: 'LOWER',
  CONCAT: 'CONCAT',
  DATE_PARSE: 'DATE_PARSE',
  PARSE_DATE: 'DATE_PARSE',
  EXCLUDE: 'EXCLUDE',
  EXCLUDE_COLUMN: 'EXCLUDE',
};

export function toBackendTransformation(
  uiTransformationType: string,
  expression?: string,
): BackendTransformation {
  const type = transformationAliases[uiTransformationType.toUpperCase()] ?? 'DIRECT';
  return expression ? { type, expression } : { type };
}
