from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}:\n{old[:160]}")
    path.write_text(text.replace(old, new, 1))


models = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/models.py"
replace_once(
    models,
    '''        if self.type == TransformationType.ARITHMETIC:\n            operator = str(self.parameters.get("operator") or "").upper()\n            if operator not in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:\n                raise ValueError("ARITHMETIC requiere operator ADD, SUBTRACT, MULTIPLY o DIVIDE")\n            if len(self.source_columns) != 2:\n                raise ValueError("ARITHMETIC requiere exactamente dos source_columns")\n''',
    '''        if self.type == TransformationType.ARITHMETIC:\n            operator = str(self.parameters.get("operator") or "").upper()\n            if operator not in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:\n                raise ValueError("ARITHMETIC requiere operator ADD, SUBTRACT, MULTIPLY o DIVIDE")\n            scalar = self.parameters.get("scalar")\n            has_scalar = scalar is not None\n            if has_scalar and (isinstance(scalar, bool) or not isinstance(scalar, (int, float))):\n                raise ValueError("ARITHMETIC parameters.scalar debe ser numérico")\n            if has_scalar:\n                if len(self.source_columns) != 1:\n                    raise ValueError("ARITHMETIC con scalar requiere exactamente un source_column")\n            elif len(self.source_columns) != 2:\n                raise ValueError("ARITHMETIC requiere dos source_columns o un source_column más parameters.scalar")\n''',
)

compiler = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_intelligent_mapping/compiler.py"
replace_once(
    compiler,
    '''    elif transformation.type == TransformationType.ARITHMETIC:\n        operator = str(transformation.parameters["operator"]).upper()\n        symbols = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}\n        left = _identifier(transformation.source_columns[0], "source_column")\n        right = _identifier(transformation.source_columns[1], "source_column")\n        expression = f'(F.col("{left}") {symbols[operator]} F.col("{right}"))'\n''',
    '''    elif transformation.type == TransformationType.ARITHMETIC:\n        operator = str(transformation.parameters["operator"]).upper()\n        symbols = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}\n        left = _identifier(transformation.source_columns[0], "source_column")\n        scalar = transformation.parameters.get("scalar")\n        if scalar is not None:\n            right_expression = _literal(scalar)\n        else:\n            right = _identifier(transformation.source_columns[1], "source_column")\n            right_expression = f'F.col("{right}")'\n        expression = f'(F.col("{left}") {symbols[operator]} {right_expression})'\n''',
)

tools = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_agents/tools.py"
replace_once(
    tools,
    '''    symbol = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}.get(\n        str(transformation.parameters.get("operator") or "").upper()\n    )\n    if transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 2 and symbol:\n        interpretation = (\n            f"Entendí tu regla así: {target_column} = "\n            f"{source_columns[0]} {symbol} {source_columns[1]}."\n        )\n    else:\n''',
    '''    symbol = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}.get(\n        str(transformation.parameters.get("operator") or "").upper()\n    )\n    scalar = transformation.parameters.get("scalar")\n    if transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 1 and symbol and scalar is not None:\n        interpretation = (\n            f"Entendí tu regla así: {target_column} = "\n            f"{source_columns[0]} {symbol} {scalar}."\n        )\n    elif transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 2 and symbol:\n        interpretation = (\n            f"Entendí tu regla así: {target_column} = "\n            f"{source_columns[0]} {symbol} {source_columns[1]}."\n        )\n    else:\n''',
)

agents = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_agents/agents.py"
replace_once(
    agents,
    '''            "Construye únicamente un contrato transformation estructurado y llama siempre "\n            "validate_derived_nl_mapping_proposal con columns_json, la regla natural exacta y "\n''',
    '''            "Construye únicamente un contrato transformation estructurado. Para porcentajes o constantes "\n            "usa ARITHMETIC con un source_column y parameters {operator, scalar}; por ejemplo 10 por ciento "\n            "se representa como operator MULTIPLY y scalar 0.10. Para operaciones columna contra columna "\n            "usa dos source_columns y no uses scalar. Llama siempre "\n            "validate_derived_nl_mapping_proposal con columns_json, la regla natural exacta y "\n''',
)

app = ROOT / "src/App.tsx"
replace_once(
    app,
    '''                const request = {\n                  ...buildAgentRequest(workflow),\n                  context: `DERIVED_NL:${naturalRule}`,\n                };\n''',
    '''                const schemaHint = (workflow.sourceColumns ?? [])\n                  .map((column) => `${column.name}:${column.type}`)\n                  .join(', ');\n                const request = {\n                  ...buildAgentRequest(workflow),\n                  context: [\n                    `DERIVED_NL:${naturalRule}`,\n                    `SCHEMA=${schemaHint}`,\n                    'CONTRATO_OBLIGATORIO=target_column,target_type,transformation.type,transformation.source_columns,transformation.parameters',\n                    'PORCENTAJES=usar ARITHMETIC con un source_column y parameters.operator=MULTIPLY + parameters.scalar decimal; 10%=0.10',\n                    'NO_SQL_NO_PYSPARK=solo contrato estructurado validable',\n                  ].join(' | '),\n                };\n''',
)

test = ROOT / "backend/deployable/silver-refinement-agent/tests/test_derived_nl_scalar_arithmetic.py"
test.write_text('''from modules.silver_agents.tools import validate_derived_nl_mapping_proposal\n\n\ndef test_derived_nl_allows_numeric_scalar_percentage():\n    result = validate_derived_nl_mapping_proposal(\n        columns_json='[{"name":"suma_asegurada","type":"NUMERIC"}]',\n        natural_rule='crear campo suma_aseguradcto = suma_asegurada * 10 por ciento',\n        proposal_json=''' + "'''" + '''{\n          "target_column":"suma_aseguradcto",\n          "target_type":"NUMERIC",\n          "transformation":{\n            "type":"ARITHMETIC",\n            "source_columns":["suma_asegurada"],\n            "parameters":{"operator":"MULTIPLY","scalar":0.10}\n          }\n        }''' + "'''" + ''',\n    )\n    assert result["valid"] is True\n    assert result["proposal"]["transformation"]["parameters"]["scalar"] == 0.10\n    assert "F.lit(0.1)" in result["compiled_preview"]\n    assert "suma_asegurada" in result["interpretation"]\n\n\ndef test_derived_nl_scalar_requires_one_source_column():\n    try:\n        validate_derived_nl_mapping_proposal(\n            columns_json='[{"name":"a","type":"NUMERIC"},{"name":"b","type":"NUMERIC"}]',\n            natural_rule='crear c = a * 10 por ciento',\n            proposal_json=''' + "'''" + '''{\n              "target_column":"c",\n              "target_type":"NUMERIC",\n              "transformation":{\n                "type":"ARITHMETIC",\n                "source_columns":["a","b"],\n                "parameters":{"operator":"MULTIPLY","scalar":0.10}\n              }\n            }''' + "'''" + ''',\n        )\n    except ValueError as exc:\n        assert "scalar requiere exactamente un source_column" in str(exc)\n    else:\n        raise AssertionError("Expected scalar/source_columns validation error")\n''')

print("P0.1 applied: DERIVED_NL scalar arithmetic + richer frontend contract + tests")
