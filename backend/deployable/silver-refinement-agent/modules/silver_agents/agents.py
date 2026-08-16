from __future__ import annotations

import os

from google.adk.agents import LlmAgent, SequentialAgent

from .tools import (
    build_notebook_blueprint,
    profile_selected_table,
    quality_rule_evidence,
    validate_business_rules,
)


def _model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def build_table_profiler_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_table_profiler",
        model=_model(),
        description="Perfila la tabla BigQuery seleccionada con métricas verificables.",
        instruction=(
            "Solicitud gobernada: {request_json}. "
            "Usa profile_selected_table exactamente una vez para la tabla source. "
            "No inventes métricas. Devuelve exclusivamente JSON válido con schema, "
            "cardinalidades, nulos, claves candidatas, partición y clustering."
        ),
        tools=[profile_selected_table],
        output_key="table_profile",
    )


def build_quality_rule_advisor_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_quality_rule_advisor",
        model=_model(),
        description="Recomienda reglas de calidad basadas en perfilamiento.",
        instruction=(
            "Solicitud: {request_json}. Perfil previo: {table_profile?}. "
            "Si el perfil no está disponible, obtenlo con profile_selected_table. "
            "Luego llama quality_rule_evidence usando el perfil JSON y "
            "{business_keys_json}. Los campos críticos con nulos deben producir "
            "NOT_NULL en estado FAILING; las claves deben evaluar NOT_NULL y UNIQUE. "
            "Propón solo reglas con evidencia, déjalas PENDING_APPROVAL y devuelve "
            "exclusivamente JSON válido."
        ),
        tools=[profile_selected_table, quality_rule_evidence],
        output_key="quality_rule_proposals",
    )


def build_business_rule_validator_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_business_rule_validator",
        model=_model(),
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
    )


def build_notebook_generator_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_notebook_generator",
        model=_model(),
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
            build_quality_rule_advisor_agent(),
            build_business_rule_validator_agent(),
            build_notebook_generator_agent(),
        ],
    )
