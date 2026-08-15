import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from .validation import (
    ensure_validated_draft,
    get_missing_draft_fields,
    validate_draft_rules
)


class DataQualityService:

    def __init__(
        self,
        repository,
        bq_client,
        get_connection_function
    ):
        self.repository = repository
        self.bq_client = bq_client
        self.get_connection = get_connection_function

    def create_draft(
        self,
        request
    ) -> dict:
        draft_id = (
            "DQDRAFT_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}"
        )

        trace_id = f"TRACE_{uuid.uuid4().hex}"

        rules = [
            rule.model_dump()
            for rule in request.rules
        ]

        draft = {
            "draft_id": draft_id,
            "trace_id": trace_id,
            "session_id": request.session_id,
            "user_email": request.requested_by,

            "config_name": request.config_name,
            "domain_name": request.domain_name,
            "description": request.description,

            "connection_id": request.connection_id,
            "dataset_id": request.dataset_id,
            "table_id": request.table_id,

            "selected_columns": request.selected_columns,
            "business_key": request.business_key,
            "date_column": request.date_column,
            "table_filter": request.table_filter,

            "related_reconciliation_id": (
                request.related_reconciliation_id
            ),
            "rules": rules
        }

        missing_fields = get_missing_draft_fields(
            draft
        )

        draft_status = (
            "WAITING_INFORMATION"
            if missing_fields
            else "READY_FOR_VALIDATION"
        )

        draft["draft_status"] = draft_status
        draft["missing_fields"] = missing_fields
        draft["validation_status"] = "PENDING"
        draft["validation_message"] = None

        self.repository.create_draft(draft)

        return {
            "draft_id": draft_id,
            "trace_id": trace_id,
            "draft_status": draft_status,
            "validation_status": "PENDING",
            "missing_fields": missing_fields,
            "message": (
                "Borrador creado y listo para validación."
                if not missing_fields
                else "Borrador creado con campos faltantes."
            )
        }

    def get_draft(
        self,
        draft_id: str
    ) -> dict:
        return self.repository.get_draft(
            draft_id
        )

    def update_draft(
        self,
        draft_id: str,
        request
    ) -> dict:
        updates = request.model_dump(
            exclude_unset=True
        )

        if "rules" in updates:
            updates["rules"] = [
                (
                    rule.model_dump()
                    if hasattr(rule, "model_dump")
                    else rule
                )
                for rule in request.rules or []
            ]

        return self.repository.update_draft(
            draft_id=draft_id,
            updates=updates
        )

    def validate_draft(
        self,
        draft_id: str
    ) -> dict:
        draft = self.repository.get_draft(
            draft_id
        )

        missing_fields = get_missing_draft_fields(
            draft
        )

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "El borrador tiene campos "
                        "obligatorios faltantes"
                    ),
                    "missing_fields": missing_fields
                }
            )

        connection = self.get_connection(
            draft["connection_id"]
        )

        if (
            connection.get("connection_type")
            != "BIGQUERY"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "El Sprint 2 solo soporta "
                    "conexiones BIGQUERY"
                )
            )

        table_ref = (
            f"{connection['project_id']}."
            f"{draft['dataset_id']}."
            f"{draft['table_id']}"
        )

        try:
            table = self.bq_client.get_table(
                table_ref
            )
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo acceder a la tabla: "
                    f"{str(error)}"
                )
            )

        schema_map = {
            field.name: field.field_type
            for field in table.schema
        }

        available_columns = set(
            schema_map.keys()
        )

        errors = []

        selected_columns = (
            draft.get("selected_columns") or []
        )

        for column in selected_columns:
            if column not in available_columns:
                errors.append(
                    f"La columna seleccionada {column} "
                    "no existe en la tabla"
                )

        business_key = (
            draft.get("business_key") or []
        )

        for column in business_key:
            if column not in available_columns:
                errors.append(
                    f"La clave {column} no existe "
                    "en la tabla"
                )

        date_column = draft.get("date_column")

        if (
            date_column
            and date_column not in available_columns
        ):
            errors.append(
                f"La columna de fecha {date_column} "
                "no existe en la tabla"
            )

        rules = draft.get("rules") or []

        rule_errors = validate_draft_rules(
            rules=rules,
            available_columns=available_columns
        )

        errors.extend(rule_errors)

        validation_status = (
            "VALIDATED"
            if not errors
            else "REJECTED"
        )

        draft_status = (
            "VALIDATED"
            if not errors
            else "WAITING_INFORMATION"
        )

        validation_message = (
            "Configuración de calidad validada correctamente."
            if not errors
            else " | ".join(errors)
        )

        self.repository.update_draft_validation(
            draft_id=draft_id,
            draft_status=draft_status,
            validation_status=validation_status,
            validation_message=validation_message
        )

        return {
            "draft_id": draft_id,
            "validation_status": validation_status,
            "validation_message": validation_message,
            "validation_errors": errors,
            "table_schema": [
                {
                    "column_name": name,
                    "data_type": data_type
                }
                for name, data_type in schema_map.items()
            ]
        }

    def confirm_draft(
        self,
        draft_id: str,
        request
    ) -> dict:
        draft = self.repository.get_draft(
            draft_id
        )

        ensure_validated_draft(draft)

        rules = draft.get("rules") or []

        if not rules:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Debe configurar al menos "
                    "una regla de calidad"
                )
            )

        connection = self.get_connection(
            draft["connection_id"]
        )

        normalized_name = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            draft["config_name"].upper()
        ).strip("_")[:35]

        suffix = draft_id[-8:].upper()

        quality_config_id = (
            f"DQ_{normalized_name}_{suffix}"
        )

        self.repository.create_confirmed_config(
            quality_config_id=quality_config_id,
            draft=draft,
            connection=connection,
            confirmed_by=request.confirmed_by,
            active_flag=request.active_flag
        )

        self.repository.create_rules(
            quality_config_id=quality_config_id,
            rules=rules
        )

        self.repository.confirm_draft(
            draft_id=draft_id,
            quality_config_id=quality_config_id
        )

        return {
            "draft_id": draft_id,
            "quality_config_id": quality_config_id,
            "status": "CONFIRMED",
            "rules_created": len(rules),
            "message": (
                "La configuración de calidad fue creada "
                "y quedó disponible para futuras ejecuciones."
            )
        }
