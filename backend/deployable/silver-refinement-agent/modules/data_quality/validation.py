from fastapi import HTTPException


SUPPORTED_RULE_TYPES = {
    "NOT_NULL",
    "UNIQUE",
    "ALLOWED_VALUES",
    "VALUE_RANGE",
    "REGEX_MATCH",
    "COLUMN_COMPARISON",
    "FRESHNESS_MAX_HOURS",
    "ROW_COUNT_MIN"
}


def get_missing_draft_fields(
    draft: dict
) -> list[str]:
    required_fields = [
        "config_name",
        "connection_id",
        "dataset_id",
        "table_id"
    ]

    missing_fields = []

    for field in required_fields:
        value = draft.get(field)

        if value is None or value == "":
            missing_fields.append(field)

    return missing_fields


def validate_rule_definition(
    rule: dict,
    available_columns: set[str]
) -> list[str]:
    errors = []

    rule_type = rule.get("rule_type")
    column_name = rule.get("column_name")
    comparison_column = rule.get(
        "comparison_column"
    )
    parameters = rule.get(
        "rule_parameters"
    ) or {}

    if rule_type not in SUPPORTED_RULE_TYPES:
        errors.append(
            f"Tipo de regla no soportado: {rule_type}"
        )
        return errors

    table_level_rules = {
        "ROW_COUNT_MIN"
    }

    if (
        rule_type not in table_level_rules
        and not column_name
    ):
        errors.append(
            f"La regla {rule_type} requiere una columna"
        )

    if (
        column_name
        and column_name not in available_columns
    ):
        errors.append(
            f"La columna {column_name} no existe en la tabla"
        )

    if rule_type == "COLUMN_COMPARISON":
        if not comparison_column:
            errors.append(
                "COLUMN_COMPARISON requiere "
                "comparison_column"
            )
        elif comparison_column not in available_columns:
            errors.append(
                f"La columna {comparison_column} "
                "no existe en la tabla"
            )

    if rule_type == "ALLOWED_VALUES":
        if not parameters.get("allowed_values"):
            errors.append(
                "ALLOWED_VALUES requiere allowed_values"
            )

    if rule_type == "VALUE_RANGE":
        if (
            "min_value" not in parameters
            and "max_value" not in parameters
        ):
            errors.append(
                "VALUE_RANGE requiere min_value "
                "o max_value"
            )

    if rule_type == "REGEX_MATCH":
        if not parameters.get("regex"):
            errors.append(
                "REGEX_MATCH requiere regex"
            )

    if rule_type == "FRESHNESS_MAX_HOURS":
        if parameters.get("max_hours") is None:
            errors.append(
                "FRESHNESS_MAX_HOURS requiere max_hours"
            )

    if rule_type == "ROW_COUNT_MIN":
        if parameters.get("min_rows") is None:
            errors.append(
                "ROW_COUNT_MIN requiere min_rows"
            )

    warning_threshold = rule.get(
        "warning_threshold",
        1.0
    )
    critical_threshold = rule.get(
        "critical_threshold",
        5.0
    )

    if warning_threshold < 0:
        errors.append(
            "warning_threshold no puede ser negativo"
        )

    if critical_threshold < warning_threshold:
        errors.append(
            "critical_threshold debe ser mayor "
            "o igual a warning_threshold"
        )

    return errors


def validate_draft_rules(
    rules: list[dict],
    available_columns: set[str]
) -> list[str]:
    errors = []

    if not rules:
        errors.append(
            "Debe configurar al menos una regla de calidad"
        )
        return errors

    for index, rule in enumerate(
        rules,
        start=1
    ):
        rule_errors = validate_rule_definition(
            rule,
            available_columns
        )

        for error in rule_errors:
            errors.append(
                f"Regla {index}: {error}"
            )

    return errors


def ensure_validated_draft(
    draft: dict
):
    if draft.get("validation_status") != "VALIDATED":
        raise HTTPException(
            status_code=400,
            detail=(
                "El borrador debe estar validado "
                "antes de confirmarse"
            )
        )
