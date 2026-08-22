from modules.silver_agents.tools import validate_derived_nl_mapping_proposal


def test_derived_nl_allows_numeric_scalar_percentage():
    result = validate_derived_nl_mapping_proposal(
        columns_json='[{"name":"suma_asegurada","type":"NUMERIC"}]',
        natural_rule='crear campo suma_aseguradcto = suma_asegurada * 10 por ciento',
        proposal_json='''{
          "target_column":"suma_aseguradcto",
          "target_type":"NUMERIC",
          "transformation":{
            "type":"ARITHMETIC",
            "source_columns":["suma_asegurada"],
            "parameters":{"operator":"MULTIPLY","scalar":0.10}
          }
        }''',
    )
    assert result["valid"] is True
    assert result["proposal"]["transformation"]["parameters"]["scalar"] == 0.10
    assert "F.lit(0.1)" in result["compiled_preview"]
    assert "suma_asegurada" in result["interpretation"]


def test_derived_nl_scalar_requires_one_source_column():
    try:
        validate_derived_nl_mapping_proposal(
            columns_json='[{"name":"a","type":"NUMERIC"},{"name":"b","type":"NUMERIC"}]',
            natural_rule='crear c = a * 10 por ciento',
            proposal_json='''{
              "target_column":"c",
              "target_type":"NUMERIC",
              "transformation":{
                "type":"ARITHMETIC",
                "source_columns":["a","b"],
                "parameters":{"operator":"MULTIPLY","scalar":0.10}
              }
            }''',
        )
    except ValueError as exc:
        assert "scalar requiere exactamente un source_column" in str(exc)
    else:
        raise AssertionError("Expected scalar/source_columns validation error")
