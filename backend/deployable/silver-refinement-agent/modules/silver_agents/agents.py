from __future__ import annotations

import os

from google.adk.agents import LlmAgent, SequentialAgent

from .finops_telemetry import build_finops_callbacks
from .tools import (
    build_notebook_blueprint,
    profile_selected_table,
    recommend_column_mappings,
    validate_derived_nl_mapping_proposal,
    validate_quality_nl_rule_proposal,
    quality_rule_evidence,
    validate_business_rules,
)


def _configure_vertex_ai() -> None:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
    location = (
        os.getenv("GOOGLE_CLOUD_LOCATION")
        or os.getenv("GEMINI_LOCATION")
        or "us-central1"
    )
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    if project:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)


def _model() -> str:
    _configure_vertex_ai()
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _telemetry(canonical_agent_name: str, model_name: str) -> dict:
    before_model, after_model = build_finops_callbacks(
        canonical_agent_name=canonical_agent_name,
        model_name=model_name,
    )
    return {
        "before_model_callback": before_model,
        "after_model_callback": after_model,
    }


def build_table_profiler_agent() -> LlmAgent:
    model = _model()
    return LlmAgent(
        name="silver_table_profiler",
        model=model,
        description="Perfila la tabla BigQuery seleccionada con métricas verificables.",
        instruction=(
            "Solicitud gobernada: {request_json}. "
            "Usa profile_selected_table exactamente una vez para la tabla source. "
            "No inventes métricas. Devuelve exclusivamente JSON válido con schema, "
            "cardinalidades, nulos, claves candidatas, partición y clustering."
        ),
        tools=[profile_selected_table],
        output_key="table_profile",
        **_telemetry("table-profiler", model),
    )


def build_mapping_advisor_agent() -> LlmAgent:
    model = _model()
    return LlmAgent(
        name="silver_mapping_advisor",
        model=model,
        description="Recomienda mapping editable desde el schema real y perfil BigQuery.",
        instruction=(
            "Solicitud gobernada: {request_json}. Perfil: {table_profile?}. "
            "Si context comienza con DERIVED_NL:, interpreta exactamente una derivación "
            "usando solo columnas reales. No generes SQL, Python, PySpark ni expresiones libres. "
            "Construye únicamente un contrato transformation estructurado y llama siempre "
            "validate_derived_nl_mapping_proposal con columns_json, la regla natural exacta y "
            "proposal_json. Devuelve exclusivamente el JSON retornado por esa tool. "
            "Para solicitudes normales usa recommend_column_mappings. Toda recomendación queda "
            "PENDING_APPROVAL y requiere confirmación humana."
        ),
        tools=[recommend_column_mappings, validate_derived_nl_mapping_proposal],
        output_key="mapping_recommendations",
        **_telemetry("mapping-advisor", model),
    )


def build_quality_rule_advisor_agent() -> LlmAgent:
    model = _model()
    return LlmAgent(
        name="silver_quality_rule_advisor",
        model=model,
        description="Recomienda reglas de calidad basadas en perfilamiento.",
        instruction=(
            "Solicitud: {request_json}. Perfil previo: {table_profile?}. "
            "Si context comienza con QUALITY_NL:, interpreta exactamente una regla de calidad "
            "usando solo columnas reales y uno de NOT_NULL, UNIQUE, ALLOWED_VALUES, VALUE_RANGE o REGEX. "
            "No generes SQL, Python, PySpark ni expresiones libres. Construye solo un contrato estructurado "
            "y llama siempre validate_quality_nl_rule_proposal con columns_json, la regla natural exacta "
            "y proposal_json. Devuelve exclusivamente el JSON retornado por esa tool. "
            "Para solicitudes normales, si falta perfil obtenlo con profile_selected_table y luego llama "
            "quality_rule_evidence usando el perfil JSON y {business_keys_json}. Toda propuesta queda "
            "PENDING_APPROVAL y requiere confirmación humana."
        ),
        tools=[profile_selected_table, quality_rule_evidence, validate_quality_nl_rule_proposal],
        output_key="quality_rule_proposals",
        **_telemetry("quality-rule-advisor", model),
    )


def build_business_rule_validator_agent() -> LlmAgent:
    model = _model()
    return LlmAgent(
        name="silver_business_rule_validator",
        model=model,
        description="Valida reglas contra el schema y contrato ejecutable.",
        instruction=(
            "Perfil: {table_profile?}. Reglas: {business_rules_json}. "
            "Si falta el perfil, obtenlo con profile_selected_table usando "
            "{request_json}. Valida las reglas usando siempre "
            "validate_business_rules. No declares válida una regla rechazada por "
            "la tool. Devuelve exclusivamente JSON válido con valid, findings y "
            "acciones de corrección."
        ),
        tools=[profile_selected_table, validate_business_rules],
        output_key="business_rule_validation",
        **_telemetry("business-rule-validator", model),
    )


def build_notebook_generator_agent() -> LlmAgent:
    model = _model()
    return LlmAgent(
        name="silver_notebook_generator",
        model=model,
        description="Genera un blueprint de notebook gobernado y ejecutable.",
        instruction=(
            "Especificación: {notebook_spec_json}. Validación de reglas: "
            "{business_rule_validation?}. Propuestas de calidad: "
            "{quality_rule_proposals?}. Usa build_notebook_blueprint. Si la "
            "validación contiene errores o faltan datos, devuelve BLOCKED. Conserva "
            "business keys, watermark, estrategia de carga, quality gates y "
            "validación post-ejecución. Devuelve exclusivamente JSON válido."
        ),
        tools=[build_notebook_blueprint],
        output_key="notebook_blueprint",
        **_telemetry("notebook-generator", model),
    )


def build_silver_orchestrator() -> SequentialAgent:
    return SequentialAgent(
        name="silver_design_orchestrator",
        description=(
            "Orquesta perfilamiento, recomendación de calidad, validación de reglas "
            "y generación de notebook para Bronze-to-Silver."
        ),
        sub_agents=[
            build_table_profiler_agent(),
            build_mapping_advisor_agent(),
            build_quality_rule_advisor_agent(),
            build_business_rule_validator_agent(),
            build_notebook_generator_agent(),
        ],
    )
