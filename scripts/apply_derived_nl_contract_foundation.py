from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text)


def replace_once(path: str, old: str, new: str, *, already: str | None = None) -> None:
    text = read(path)
    if already and already in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:160]!r}")
    write(path, text.replace(old, new, 1))


# 1) Executable mapping contract: safe arithmetic whitelist.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/models.py",
    '    DATE_PARSE = "DATE_PARSE"\n    EXCLUDE = "EXCLUDE"',
    '    DATE_PARSE = "DATE_PARSE"\n    ARITHMETIC = "ARITHMETIC"\n    EXCLUDE = "EXCLUDE"',
    already='    ARITHMETIC = "ARITHMETIC"',
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/models.py",
    '        if self.type == TransformationType.DATE_PARSE and not self.parameters.get("format"):\n            raise ValueError("DATE_PARSE requiere parameters.format")\n        return self',
    '        if self.type == TransformationType.DATE_PARSE and not self.parameters.get("format"):\n            raise ValueError("DATE_PARSE requiere parameters.format")\n        if self.type == TransformationType.ARITHMETIC:\n            operator = str(self.parameters.get("operator") or "").upper()\n            if operator not in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:\n                raise ValueError("ARITHMETIC requiere operator ADD, SUBTRACT, MULTIPLY o DIVIDE")\n            if len(self.source_columns) != 2:\n                raise ValueError("ARITHMETIC requiere exactamente dos source_columns")\n        return self',
    already='ARITHMETIC requiere operator ADD, SUBTRACT, MULTIPLY o DIVIDE',
)

# 2) Compiler: no free-form expressions, only validated operator symbols.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/compiler.py",
    '    if source is None and transformation.type != TransformationType.CONCAT:\n        raise ValueError(f"La columna {target} no tiene fuente")',
    '    if source is None and transformation.type not in {TransformationType.CONCAT, TransformationType.ARITHMETIC}:\n        raise ValueError(f"La columna {target} no tiene fuente")',
    already='TransformationType.CONCAT, TransformationType.ARITHMETIC',
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/compiler.py",
    '    elif transformation.type == TransformationType.DATE_PARSE:\n        fmt = transformation.parameters["format"]\n        expression = f\'F.to_date(F.col("{source}"), {fmt!r})\'\n    else:',
    '    elif transformation.type == TransformationType.DATE_PARSE:\n        fmt = transformation.parameters["format"]\n        expression = f\'F.to_date(F.col("{source}"), {fmt!r})\'\n    elif transformation.type == TransformationType.ARITHMETIC:\n        operator = str(transformation.parameters["operator"]).upper()\n        symbols = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}\n        left = _identifier(transformation.source_columns[0], "source_column")\n        right = _identifier(transformation.source_columns[1], "source_column")\n        expression = f\'(F.col("{left}") {symbols[operator]} F.col("{right}"))\'\n    else:',
    already='symbols = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}',
)

# 3) Persist structured transformations + NL traceability in Silver workflow.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py",
    '''class SilverMappingColumn(BaseModel):\n    name: str = Field(min_length=1, max_length=300)\n    data_type: str = Field(min_length=1, max_length=200)\n    nullable: bool = True\n    source_column: str | None = Field(default=None, max_length=300)\n    transformation: str | None = Field(default=None, max_length=8000)\n    description: str | None = Field(default=None, max_length=2000)\n\n    @model_validator(mode="after")\n    def validate_mapping_source(self) -> "SilverMappingColumn":\n        if not self.source_column and not self.transformation:\n            raise ValueError("Cada columna Silver debe indicar source_column o transformation")\n        return self''',
    '''class SilverMappingColumn(BaseModel):\n    name: str = Field(min_length=1, max_length=300)\n    data_type: str = Field(min_length=1, max_length=200)\n    nullable: bool = True\n    source_column: str | None = Field(default=None, max_length=300)\n    source_columns: list[str] = Field(default_factory=list)\n    transformation: str | dict[str, Any] | None = None\n    derivation_mode: str | None = Field(default=None, max_length=50)\n    natural_rule: str | None = Field(default=None, max_length=4000)\n    description: str | None = Field(default=None, max_length=2000)\n\n    @model_validator(mode="after")\n    def validate_mapping_source(self) -> "SilverMappingColumn":\n        if not self.source_column and not self.source_columns and not self.transformation:\n            raise ValueError("Cada columna Silver debe indicar source_column/source_columns o transformation")\n        if self.derivation_mode == "DERIVED_NL" and not self.natural_rule:\n            raise ValueError("DERIVED_NL requiere natural_rule para trazabilidad")\n        return self''',
    already='    source_columns: list[str] = Field(default_factory=list)',
)

# 4) Impact analysis + persistence validate all structured source references.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    '''            "source_column": raw.get("source_column") or raw.get("sourceColumn"),\n            "transformation": raw.get("transformation") or raw.get("transformation_type") or raw.get("transformationType"),\n        }''',
    '''            "source_column": raw.get("source_column") or raw.get("sourceColumn"),\n            "source_columns": raw.get("source_columns") or raw.get("sourceColumns") or [],\n            "transformation": raw.get("transformation") or raw.get("transformation_type") or raw.get("transformationType"),\n            "derivation_mode": raw.get("derivation_mode") or raw.get("derivationMode"),\n            "natural_rule": raw.get("natural_rule") or raw.get("naturalRule"),\n        }''',
    already='            "derivation_mode": raw.get("derivation_mode")',
)
old_unknown = '''        source_columns = {column.name for column in current.schema_context.columns}\n        unknown = sorted({\n            column.source_column\n            for column in request.columns\n            if column.source_column and column.source_column not in source_columns\n        })\n        if unknown:\n            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))'''
new_unknown = '''        source_columns = {column.name for column in current.schema_context.columns}\n        referenced_columns = {\n            reference\n            for column in request.columns\n            for reference in ([column.source_column] if column.source_column else []) + list(column.source_columns)\n        }\n        unknown = sorted(referenced_columns - source_columns)\n        if unknown:\n            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))'''
text = read("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py")
if new_unknown not in text:
    if text.count(old_unknown) != 1:
        raise SystemExit("Expected one save_mapping_version source validation block")
    write("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py", text.replace(old_unknown, new_unknown, 1))

old_spec_unknown = '''        source_columns = {column.name for column in current.schema_context.columns}\n        unknown = sorted({column.source_column for column in request.columns if column.source_column and column.source_column not in source_columns})\n        if unknown:\n            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))'''
new_spec_unknown = '''        source_columns = {column.name for column in current.schema_context.columns}\n        referenced_columns = {\n            reference\n            for column in request.columns\n            for reference in ([column.source_column] if column.source_column else []) + list(column.source_columns)\n        }\n        unknown = sorted(referenced_columns - source_columns)\n        if unknown:\n            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))'''
text = read("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py")
if new_spec_unknown not in text:
    if old_spec_unknown not in text:
        raise SystemExit("save_specification source validation block not found")
    write("backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py", text.replace(old_spec_unknown, new_spec_unknown, 1))

# 5) Artifact contract keeps derivation metadata.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_refinement/artifact_models.py",
    '    source_column: str | None = None\n    transformation: MappingTransformation | str | None = None\n    include: bool = True',
    '    source_column: str | None = None\n    source_columns: list[str] = Field(default_factory=list)\n    transformation: MappingTransformation | str | None = None\n    derivation_mode: str | None = None\n    natural_rule: str | None = None\n    include: bool = True',
    already='    derivation_mode: str | None = None',
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_refinement/artifact_models.py",
    '        source = self.source_column or self.name\n        payload["source_columns"] = [source]',
    '        source = self.source_column or self.name\n        payload["source_columns"] = self.source_columns or [source]',
    already='payload["source_columns"] = self.source_columns or [source]',
)

# 6) Frontend type and typed transformation payloads.
replace_once(
    "src/transformations.ts",
    "  | 'DATE_PARSE'\n  | 'EXCLUDE';",
    "  | 'DATE_PARSE'\n  | 'ARITHMETIC'\n  | 'EXCLUDE';",
    already="  | 'ARITHMETIC'",
)
replace_once(
    "src/transformations.ts",
    "  DATE_PARSE: 'DATE_PARSE',\n  PARSE_DATE: 'DATE_PARSE',",
    "  DATE_PARSE: 'DATE_PARSE',\n  PARSE_DATE: 'DATE_PARSE',\n  ARITHMETIC: 'ARITHMETIC',",
    already="  ARITHMETIC: 'ARITHMETIC'",
)
replace_once(
    "src/types.ts",
    '''  parameters?: Record<string, unknown>;\n  confidence?: number;''',
    '''  parameters?: Record<string, unknown>;\n  sourceColumns?: string[];\n  derivationMode?: 'DERIVED_NL';\n  naturalRule?: string;\n  confidence?: number;''',
    already="  derivationMode?: 'DERIVED_NL';",
)

# Preserve structured recommendation fields when hydrating agent output.
replace_once(
    "src/App.tsx",
    '''      parameters:\n        transformation.parameters && typeof transformation.parameters === 'object'\n          ? transformation.parameters as Record<string, unknown>\n          : {},\n      confidence:''',
    '''      parameters:\n        transformation.parameters && typeof transformation.parameters === 'object'\n          ? transformation.parameters as Record<string, unknown>\n          : {},\n      sourceColumns: Array.isArray(transformation.source_columns)\n        ? transformation.source_columns.map(String)\n        : undefined,\n      derivationMode: column.derivation_mode === 'DERIVED_NL' ? 'DERIVED_NL' : undefined,\n      naturalRule: typeof column.natural_rule === 'string' ? column.natural_rule : undefined,\n      confidence:''',
    already="      derivationMode: column.derivation_mode === 'DERIVED_NL'",
)

# Mapping impact/save payload becomes structured and retains NL traceability.
replace_once(
    "src/App.tsx",
    '''                    source_column: rule.sourceColumn || null,\n                    transformation: toBackendTransformation(rule.transformationType),\n                  })),''',
    '''                    source_column: rule.sourceColumn || null,\n                    source_columns: rule.sourceColumns?.length\n                      ? rule.sourceColumns\n                      : rule.sourceColumn ? [rule.sourceColumn] : [],\n                    transformation: {\n                      type: toBackendTransformation(rule.transformationType),\n                      source_columns: rule.sourceColumns?.length\n                        ? rule.sourceColumns\n                        : rule.sourceColumn ? [rule.sourceColumn] : [],\n                      parameters: rule.parameters ?? {},\n                    },\n                    derivation_mode: rule.derivationMode ?? null,\n                    natural_rule: rule.naturalRule ?? null,\n                  })),''',
    already='                    derivation_mode: rule.derivationMode ?? null,',
)

# Artifact package contract also carries structured transformation.
replace_once(
    "src/App.tsx",
    '''      source_column: rule.sourceColumn,\n      transformation: toBackendTransformation(rule.transformationType),\n      include: true,''',
    '''      source_column: rule.sourceColumn || null,\n      source_columns: rule.sourceColumns?.length\n        ? rule.sourceColumns\n        : rule.sourceColumn ? [rule.sourceColumn] : [],\n      transformation: {\n        type: toBackendTransformation(rule.transformationType),\n        source_columns: rule.sourceColumns?.length\n          ? rule.sourceColumns\n          : rule.sourceColumn ? [rule.sourceColumn] : [],\n        parameters: rule.parameters ?? {},\n      },\n      derivation_mode: rule.derivationMode ?? null,\n      natural_rule: rule.naturalRule ?? null,\n      include: true,''',
    already='      derivation_mode: rule.derivationMode ?? null,',
)

# 7) Focused tests for safe compiler + persisted traceability.
test_path = ROOT / "backend/deployable/silver-refinement-agent/tests/test_derived_nl_contract.py"
test_path.write_text('''import pytest\n\nfrom modules.silver_intelligent_mapping.compiler import compile_pyspark_expression\nfrom modules.silver_intelligent_mapping.models import (\n    IntelligentMappingColumn, MappingTransformation, TransformationType,\n)\nfrom modules.silver_workflow.models import SilverMappingColumn\n\n\ndef test_arithmetic_derivation_compiles_from_structured_contract_only():\n    column = IntelligentMappingColumn(\n        source_column=None,\n        target_column="monto_neto",\n        target_type="NUMERIC",\n        nullable=True,\n        transformation=MappingTransformation(\n            type=TransformationType.ARITHMETIC,\n            source_columns=["monto_bruto", "descuento"],\n            parameters={"operator": "SUBTRACT"},\n        ),\n        requires_approval=True,\n    )\n\n    expression = compile_pyspark_expression(column)\n\n    assert 'F.col("monto_bruto") - F.col("descuento")' in expression\n    assert '.alias("monto_neto")' in expression\n    assert 'decimal(38,9)' in expression\n\n\ndef test_arithmetic_rejects_non_whitelisted_operator():\n    with pytest.raises(ValueError, match="ARITHMETIC requiere operator"):\n        MappingTransformation(\n            type=TransformationType.ARITHMETIC,\n            source_columns=["monto_bruto", "descuento"],\n            parameters={"operator": "EVAL"},\n        )\n\n\ndef test_workflow_mapping_preserves_derived_nl_traceability():\n    column = SilverMappingColumn(\n        name="monto_neto",\n        data_type="NUMERIC",\n        source_columns=["monto_bruto", "descuento"],\n        transformation={\n            "type": "ARITHMETIC",\n            "source_columns": ["monto_bruto", "descuento"],\n            "parameters": {"operator": "SUBTRACT"},\n        },\n        derivation_mode="DERIVED_NL",\n        natural_rule="Crear monto_neto restando descuento a monto_bruto",\n    )\n\n    payload = column.model_dump(mode="json")\n    assert payload["derivation_mode"] == "DERIVED_NL"\n    assert payload["natural_rule"].startswith("Crear monto_neto")\n    assert payload["transformation"]["parameters"]["operator"] == "SUBTRACT"\n''')

print("PASS: fundamento ejecutable DERIVED_NL aplicado.")
print("ARITHMETIC usa whitelist estructurada; no se persiste ni ejecuta código libre desde lenguaje natural.")
