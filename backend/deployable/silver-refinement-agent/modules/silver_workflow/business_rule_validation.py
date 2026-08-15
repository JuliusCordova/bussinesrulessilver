from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from .models import (
    BusinessRule,
    BusinessRulesSection,
    BusinessRuleStatus,
    SaveBusinessRulesDraftRequest,
    SchemaContextEvidence,
)


class BusinessRuleValidationError(ValueError):
    pass


_FORBIDDEN_SQL_KEYWORDS = {
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DROP",
    "EXECUTE",
    "GRANT",
    "INSERT",
    "MERGE",
    "REVOKE",
    "SELECT",
    "TRUNCATE",
    "UPDATE",
}

_FORBIDDEN_EXPRESSION_FRAGMENTS = (";", "--", "/*", "*/")
_ALLOWED_EXPRESSION_CHARACTERS = re.compile(
    r"^[A-Za-z0-9_.$`\s(),+\-*/%<>=!'\":\[\]]+$"
)
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def validate_expression(expression: str) -> None:
    candidate = expression.strip()
    if not candidate:
        raise BusinessRuleValidationError("La expresión de la regla no puede estar vacía")

    if any(fragment in candidate for fragment in _FORBIDDEN_EXPRESSION_FRAGMENTS):
        raise BusinessRuleValidationError(
            "La expresión contiene separadores o comentarios SQL no permitidos"
        )

    if not _ALLOWED_EXPRESSION_CHARACTERS.fullmatch(candidate):
        raise BusinessRuleValidationError(
            "La expresión contiene caracteres fuera de la gramática permitida"
        )

    if not _has_balanced_parentheses(candidate):
        raise BusinessRuleValidationError(
            "La expresión contiene paréntesis desbalanceados"
        )

    tokens = {token.upper() for token in _IDENTIFIER.findall(_without_literals(candidate))}
    forbidden = sorted(tokens & _FORBIDDEN_SQL_KEYWORDS)
    if forbidden:
        raise BusinessRuleValidationError(
            "La expresión contiene operaciones SQL no permitidas: "
            + ", ".join(forbidden)
        )


def validate_rules_against_schema(
    rules: Iterable[BusinessRule],
    schema_context: SchemaContextEvidence,
    *,
    require_enabled: bool = False,
) -> list[BusinessRule]:
    normalized_rules = list(rules)
    if not normalized_rules:
        raise BusinessRuleValidationError(
            "Debe existir al menos una Business Rule"
        )

    known_columns = {
        column.name.casefold(): column.name for column in schema_context.columns
    }
    semantic_keys: set[tuple[str, str, str]] = set()

    for rule in normalized_rules:
        unknown_columns = [
            column
            for column in rule.source_columns
            if column.casefold() not in known_columns
        ]
        if unknown_columns:
            raise BusinessRuleValidationError(
                f"La regla {rule.rule_id} referencia columnas fuente inexistentes: "
                + ", ".join(sorted(unknown_columns))
            )

        validate_expression(rule.expression)

        semantic_key = (
            rule.name.strip().casefold(),
            rule.rule_type.value,
            " ".join(rule.expression.split()).casefold(),
        )
        if semantic_key in semantic_keys:
            raise BusinessRuleValidationError(
                f"La regla {rule.rule_id} duplica semánticamente otra regla"
            )
        semantic_keys.add(semantic_key)

    if require_enabled and not any(rule.enabled for rule in normalized_rules):
        raise BusinessRuleValidationError(
            "La confirmación requiere al menos una Business Rule habilitada"
        )

    return normalized_rules


def build_draft_section(
    request: SaveBusinessRulesDraftRequest,
    *,
    schema_context: SchemaContextEvidence,
    updated_at: datetime,
) -> BusinessRulesSection:
    rules = validate_rules_against_schema(request.rules, schema_context)
    return BusinessRulesSection(
        status=BusinessRuleStatus.DRAFT,
        rules=rules,
        last_modified_by=request.authored_by,
        last_modified_at=updated_at,
        confirmation_reason=None,
        confirmed_by=None,
        confirmed_at=None,
    )


def _has_balanced_parentheses(expression: str) -> bool:
    depth = 0
    quote: str | None = None
    escaped = False

    for character in expression:
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote is not None:
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if quote is not None:
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False

    return depth == 0 and quote is None


def _without_literals(expression: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False

    for character in expression:
        if escaped:
            escaped = False
            if quote is None:
                result.append(character)
            continue
        if character == "\\" and quote is not None:
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            result.append(" ")
            continue
        result.append(character if quote is None else " ")

    return "".join(result)
