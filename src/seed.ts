import type { BusinessRule, SeedColumn } from './types';

export const seedSource = {
  projectId: 'proyectopersonal-480420',
  sourceDataset: 'seguros_bronce',
  sourceTable: 'cat_producto',
  targetDataset: 'seguros_silver',
  targetTable: 'cat_producto',
  businessKey: 'producto_id',
  watermark: 'bronze_fecha_ingesta',
  initialWatermark: '2026-07-31T20:30:00Z',
  clusteringColumns: ['producto_id', 'ramo_id', 'bronze_registro_id', 'bronze_carga_id'],
  metric: 'prima_base',
};

export const seedColumns: SeedColumn[] = [
  { name: 'producto_id', type: 'STRING', usage: 'business_key' },
  { name: 'ramo_id', type: 'STRING', usage: 'dimension' },
  { name: 'nombre_producto', type: 'STRING', usage: 'dimension' },
  { name: 'moneda', type: 'STRING', usage: 'rule' },
  { name: 'periodicidad', type: 'STRING', usage: 'rule' },
  { name: 'prima_base', type: 'NUMERIC', usage: 'metric' },
  { name: 'bronze_registro_id', type: 'STRING', usage: 'traceability' },
  { name: 'bronze_carga_id', type: 'STRING', usage: 'traceability' },
  { name: 'bronze_fecha_ingesta', type: 'TIMESTAMP', usage: 'watermark' },
  { name: 'bronze_archivo_origen', type: 'STRING', usage: 'traceability' },
  { name: 'bronze_hash_origen', type: 'STRING', usage: 'traceability' },
  { name: 'bronze_estado_registro', type: 'STRING', usage: 'rule' },
];

export const businessRules: BusinessRule[] = [
  {
    name: 'producto_id es obligatorio y business key',
    severity: 'HIGH',
    expression: 'producto_id IS NOT NULL',
  },
  {
    name: 'moneda solo permite PEN o USD',
    severity: 'HIGH',
    expression: "moneda IN ('PEN', 'USD')",
  },
  {
    name: 'periodicidad solo permite MENSUAL o ANUAL',
    severity: 'HIGH',
    expression: "periodicidad IN ('MENSUAL', 'ANUAL')",
  },
  {
    name: 'bronze_estado_registro debe ser RECIBIDO',
    severity: 'HIGH',
    expression: "bronze_estado_registro = 'RECIBIDO'",
  },
  {
    name: 'Conservar trazabilidad bronze_*',
    severity: 'MEDIUM',
    expression: 'bronze_registro_id, bronze_carga_id, bronze_hash_origen must be preserved',
  },
  {
    name: 'Control SUM prima_base para reconciliacion posterior',
    severity: 'MEDIUM',
    expression: 'SUM(prima_base) source = SUM(prima_base) target',
  },
];
