from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Protocol

from .models import (
    BusinessRule,
    BusinessRuleProposalMetadata,
    BusinessRulesSection,
    BusinessRuleSeverity,
    BusinessRuleStatus,
    BusinessRuleType,
    GenerateBusinessRulesRequest,
    SchemaColumnEvidence,
    SilverWorkflowRecord,
)


class BusinessRuleProposalGenerator(Protocol):
    def generate(
        self,
        workflow: SilverWorkflowRecord,
        request: GenerateBusinessRulesRequest,
        *,
        generated_by: str,
        idempotency_key: str,
        generated_at: datetime,
    ) -> BusinessRulesSection:
        ...


class DeterministicBusinessRuleProposalGenerator:
    """Auditable schema-based proposal generator used until an LLM adapter is enabled.

    The generator never confirms rules. It creates conservative structural proposals
    from persisted schema evidence so the full workflow contract can be validated
    deterministically in local and zero-traffic runtime gates.
    """

    model_name = "deterministic-schema-proposal-v1"
    prompt_template_version = "business-rules-schema-v1"

    def generate(
        self,
        workflow: SilverWorkflowRecord,
        request: GenerateBusinessRulesRequest,
        *,
        generated_by: str,
        idempotency_key: str,
        generated_at: datetime,
    ) -> BusinessRulesSection:
        if workflow.schema_context is None:
            raise ValueError("El workflow no contiene contexto de esquema confirmado")

        ordered_columns = sorted(
            workflow.schema_context.columns,
            key=lambda column: column.ordinal_position or 1_000_000,
        )
        rules = self._candidate_rules(ordered_columns, request.max_rules)
        proposal_id = self._proposal_id(
            workflow.workflow_id,
            workflow.version,
            idempotency_key,
        )
        proposal_metadata = BusinessRuleProposalMetadata(
            proposal_id=proposal_id,
            model_name=self.model_name,
            prompt_template_version=self.prompt_template_version,
            generated_at=generated_at,
            generated_by=generated_by,
            source_workflow_version=workflow.version,
            idempotency_key=idempotency_key,
            latency_ms=0,
            token_usage={},
            metadata={
                "provider": "deterministic",
                "generation_reason": request.generation_reason,
                "requested_max_rules": request.max_rules,
                "schema_column_count": len(ordered_columns),
                "human_confirmation_required": True,
                "limitations": (
                    "Structural schema proposal only; no business semantics inferred"
                ),
            },
        )
        return BusinessRulesSection(
            status=BusinessRuleStatus.PROPOSED,
            rules=rules,
            proposal_id=proposal_id,
            proposal_metadata=proposal_metadata,
            last_modified_by=generated_by,
            last_modified_at=generated_at,
        )

    @classmethod
    def _candidate_rules(
        cls,
        columns: list[SchemaColumnEvidence],
        max_rules: int,
    ) -> list[BusinessRule]:
        candidates: list[BusinessRule] = []

        for column in columns:
            if not column.nullable:
                candidates.append(
                    cls._not_null_rule(
                        column,
                        index=len(candidates) + 1,
                        severity=BusinessRuleSeverity.ERROR,
                        basis="schema_non_nullable",
                    )
                )
                if len(candidates) >= max_rules:
                    return candidates

        for column in columns:
            if cls._is_string_type(column.data_type):
                candidates.append(
                    BusinessRule(
                        rule_id=cls._rule_id(
                            len(candidates) + 1,
                            column.name,
                            "trimmed",
                        ),
                        name=f"Normalizar espacios de {column.name}",
                        description=(
                            f"Propone que {column.name} se conserve sin espacios "
                            "laterales."
                        ),
                        rule_type=BusinessRuleType.STANDARDIZATION,
                        expression=f"{column.name} = TRIM({column.name})",
                        severity=BusinessRuleSeverity.WARNING,
                        enabled=True,
                        source_columns=[column.name],
                        target_columns=[column.name],
                        rationale=(
                            "Las columnas de texto suelen requerir normalización "
                            "antes del refinamiento Silver."
                        ),
                        metadata={"proposal_basis": "schema_string_type"},
                    )
                )
                if len(candidates) >= max_rules:
                    return candidates

        if not candidates:
            first_column = columns[0]
            candidates.append(
                cls._not_null_rule(
                    first_column,
                    index=1,
                    severity=BusinessRuleSeverity.WARNING,
                    basis="first_column_candidate",
                )
            )

        return candidates

    @classmethod
    def _not_null_rule(
        cls,
        column: SchemaColumnEvidence,
        *,
        index: int,
        severity: BusinessRuleSeverity,
        basis: str,
    ) -> BusinessRule:
        return BusinessRule(
            rule_id=cls._rule_id(index, column.name, "not_null"),
            name=f"Completitud de {column.name}",
            description=f"Propone que {column.name} no contenga valores nulos.",
            rule_type=BusinessRuleType.VALIDATION,
            expression=f"{column.name} IS NOT NULL",
            severity=severity,
            enabled=True,
            source_columns=[column.name],
            target_columns=[column.name],
            rationale=(
                "La regla se deriva únicamente de evidencia estructural y debe "
                "ser confirmada por una persona."
            ),
            metadata={"proposal_basis": basis},
        )

    @staticmethod
    def _is_string_type(data_type: str) -> bool:
        normalized = data_type.strip().upper()
        return any(
            marker in normalized
            for marker in ("STRING", "CHAR", "TEXT", "VARCHAR")
        )

    @staticmethod
    def _rule_id(index: int, column_name: str, suffix: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", column_name.casefold()).strip("_")
        return f"proposal_{index}_{slug or 'column'}_{suffix}"

    @staticmethod
    def _proposal_id(
        workflow_id: str,
        workflow_version: int,
        idempotency_key: str,
    ) -> str:
        source = f"{workflow_id}:{workflow_version}:{idempotency_key}".encode()
        digest = hashlib.sha256(source).hexdigest()[:24]
        return f"proposal_{digest}"
