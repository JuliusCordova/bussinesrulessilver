from __future__ import annotations

from fastapi.testclient import TestClient

from modules.silver_refinement.app import app


client = TestClient(app)
SCHEMA = [
    {"name": "ramo_id", "type": "STRING"},
    {"name": "moneda", "type": "STRING"},
    {"name": "edad", "type": "INT64"},
]


def test_validate_srl_check_not_null() -> None:
    response = client.post(
        "/silver-rules/validate",
        json={
            "srl": "CHECK ramo_id NOT_NULL\nON_FAIL BLOCK_LOAD",
            "schema": SCHEMA,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["ast"]["family"] == "CHECK"
    assert body["compiled"]["rule_type"] == "NOT_NULL"
    assert body["compiled"]["runtime_action"] == "BLOCK_LOAD"


def test_validate_srl_check_allowed_values() -> None:
    response = client.post(
        "/silver-rules/validate",
        json={
            "srl": 'CHECK moneda IN ["PEN", "USD"] ON_FAIL WARN',
            "schema": SCHEMA,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["compiled"]["parameters"] == {
        "allowed_values": ["PEN", "USD"]
    }


def test_validate_srl_rejects_unknown_column_with_422() -> None:
    response = client.post(
        "/silver-rules/validate",
        json={
            "srl": "CHECK fantasma NOT_NULL ON_FAIL WARN",
            "schema": SCHEMA,
        },
    )
    assert response.status_code == 422
    assert "Columna inexistente" in response.json()["detail"]
