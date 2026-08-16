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
            "Usa profile_selected_table exactamente una vez con la tabla indicada. "
            "No inventes métricas. Devuelve JSON válido con schema, cardinalidades, "
            "nulos, partición, clustering y alertas observables."
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
            "Lee el perfil disponible en {table_profile}. Llama quality_rule_evidence "
            "con ese JSON. Propón solo reglas respaldadas por evidencia. Cada regla "
            "debe incluir rule_name, rule_dimension, rule_type, column_name, "
            "rule_parameters, severity_level, confidence y rationale. Marca las "
            "propuestas como PENDING_APPROVAL. Devuelve JSON válido."
        ),
        tools=[quality_rule_evidence],
        output_key="quality_rule_proposals",
    )


def build_business_rule_validator_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_business_rule_validator",
        model=_model(),
        description="Valida reglas contra el schema y contrato ejecutable.",
        instruction=(
            "Valida las reglas recibidas contra {table_profile}. Usa siempre "
            "validate_business_rules. No declares una regla válida si la tool la "
            "rechaza. Explica errores accionables y devuelve JSON válido."
        ),
        tools=[validate_business_rules],
        output_key="business_rule_validation",
    )


def build_notebook_generator_agent() -> LlmAgent:
    return LlmAgent(
        name="silver_notebook_generator",
        model=_model(),
        description="Genera un blueprint de notebook gobernado y ejecutable.",
        instruction=(
            "Genera el notebook solo si las reglas están aprobadas o validadas. Usa "
            "build_notebook_blueprint con la especificación completa. Conserva "
            "business keys, watermark, estrategia de carga, quality gates y "
            "validación post-ejecución. Devuelve JSON válido; si falta información, "
            "devuelve BLOCKED con los campos faltantes."
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
