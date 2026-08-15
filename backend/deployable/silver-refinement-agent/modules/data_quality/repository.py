import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from google.cloud import bigquery


class DataQualityRepository:

    def __init__(
        self,
        client: bigquery.Client,
        project_id: str,
        dataset_id: str
    ):
        self.client = client
        self.project_id = project_id
        self.dataset_id = dataset_id

    def list_rule_types(self) -> list[dict]:
        query = f"""
        SELECT
          rule_type,
          rule_name,
          rule_dimension,
          description,
          applicable_data_types,
          requires_column,
          requires_comparison_column,
          requires_parameters,
          default_warning_threshold,
          default_critical_threshold
        FROM `{self.project_id}.{self.dataset_id}.data_quality_rule_type`
        WHERE active_flag = TRUE
        ORDER BY rule_dimension, rule_name
        """

        rows = self.client.query(query).result()

        return [
            dict(row.items())
            for row in rows
        ]

    def list_quality_configs(
        self,
        active_only: bool = True
    ) -> list[dict]:
        where_clause = (
            "WHERE active_flag = TRUE"
            if active_only
            else ""
        )

        query = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.data_quality_config`
        {where_clause}
        ORDER BY config_name
        """

        rows = self.client.query(query).result()

        return [
            dict(row.items())
            for row in rows
        ]

    def get_quality_config(
        self,
        quality_config_id: str
    ) -> dict:
        query = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.data_quality_config`
        WHERE quality_config_id = @quality_config_id
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "quality_config_id",
                    "STRING",
                    quality_config_id
                )
            ]
        )

        rows = list(
            self.client.query(
                query,
                job_config=job_config
            ).result()
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No existe la configuración "
                    f"{quality_config_id}"
                )
            )

        return dict(rows[0].items())

    def create_draft(
        self,
        draft: dict
    ) -> None:
        query = f"""
        INSERT INTO
        `{self.project_id}.{self.dataset_id}.data_quality_config_draft`
        (
          draft_id,
          trace_id,
          session_id,
          user_email,

          config_name,
          domain_name,
          description,

          connection_id,
          dataset_id,
          table_id,

          selected_columns,
          business_key,
          date_column,
          table_filter,

          related_reconciliation_id,
          draft_rules,

          draft_status,
          missing_fields,
          validation_status,
          validation_message,

          created_at,
          updated_at
        )
        VALUES
        (
          @draft_id,
          @trace_id,
          @session_id,
          @user_email,

          @config_name,
          @domain_name,
          @description,

          @connection_id,
          @dataset_id,
          @table_id,

          @selected_columns,
          @business_key,
          @date_column,
          @table_filter,

          @related_reconciliation_id,
          PARSE_JSON(@draft_rules),

          @draft_status,
          @missing_fields,
          @validation_status,
          @validation_message,

          CURRENT_TIMESTAMP(),
          CURRENT_TIMESTAMP()
        )
        """

        parameters = [
            bigquery.ScalarQueryParameter(
                "draft_id",
                "STRING",
                draft["draft_id"]
            ),
            bigquery.ScalarQueryParameter(
                "trace_id",
                "STRING",
                draft["trace_id"]
            ),
            bigquery.ScalarQueryParameter(
                "session_id",
                "STRING",
                draft.get("session_id")
            ),
            bigquery.ScalarQueryParameter(
                "user_email",
                "STRING",
                draft.get("user_email")
            ),
            bigquery.ScalarQueryParameter(
                "config_name",
                "STRING",
                draft.get("config_name")
            ),
            bigquery.ScalarQueryParameter(
                "domain_name",
                "STRING",
                draft.get("domain_name")
            ),
            bigquery.ScalarQueryParameter(
                "description",
                "STRING",
                draft.get("description")
            ),
            bigquery.ScalarQueryParameter(
                "connection_id",
                "STRING",
                draft.get("connection_id")
            ),
            bigquery.ScalarQueryParameter(
                "dataset_id",
                "STRING",
                draft.get("dataset_id")
            ),
            bigquery.ScalarQueryParameter(
                "table_id",
                "STRING",
                draft.get("table_id")
            ),
            bigquery.ArrayQueryParameter(
                "selected_columns",
                "STRING",
                draft.get("selected_columns") or []
            ),
            bigquery.ArrayQueryParameter(
                "business_key",
                "STRING",
                draft.get("business_key") or []
            ),
            bigquery.ScalarQueryParameter(
                "date_column",
                "STRING",
                draft.get("date_column")
            ),
            bigquery.ScalarQueryParameter(
                "table_filter",
                "STRING",
                draft.get("table_filter")
            ),
            bigquery.ScalarQueryParameter(
                "related_reconciliation_id",
                "STRING",
                draft.get("related_reconciliation_id")
            ),
            bigquery.ScalarQueryParameter(
                "draft_rules",
                "STRING",
                json.dumps(
                    draft.get("rules") or [],
                    ensure_ascii=False
                )
            ),
            bigquery.ScalarQueryParameter(
                "draft_status",
                "STRING",
                draft.get("draft_status")
            ),
            bigquery.ArrayQueryParameter(
                "missing_fields",
                "STRING",
                draft.get("missing_fields") or []
            ),
            bigquery.ScalarQueryParameter(
                "validation_status",
                "STRING",
                draft.get("validation_status")
            ),
            bigquery.ScalarQueryParameter(
                "validation_message",
                "STRING",
                draft.get("validation_message")
            )
        ]

        job_config = bigquery.QueryJobConfig(
            query_parameters=parameters
        )

        self.client.query(
            query,
            job_config=job_config
        ).result()

    def get_draft(
        self,
        draft_id: str
    ) -> dict:
        query = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.data_quality_config_draft`
        WHERE draft_id = @draft_id
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "draft_id",
                    "STRING",
                    draft_id
                )
            ]
        )

        rows = list(
            self.client.query(
                query,
                job_config=job_config
            ).result()
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No existe el borrador {draft_id}"
            )

        draft = dict(rows[0].items())

        draft_rules = draft.get("draft_rules")

        if draft_rules is None:
            draft["rules"] = []
        elif isinstance(draft_rules, str):
            draft["rules"] = json.loads(draft_rules)
        else:
            draft["rules"] = draft_rules

        return draft

    def update_draft(
        self,
        draft_id: str,
        updates: dict
    ) -> dict:
        assignments = []
        parameters = [
            bigquery.ScalarQueryParameter(
                "draft_id",
                "STRING",
                draft_id
            )
        ]

        scalar_string_fields = [
            "config_name",
            "domain_name",
            "description",
            "date_column",
            "table_filter",
            "related_reconciliation_id"
        ]

        for field in scalar_string_fields:
            if field in updates:
                assignments.append(
                    f"{field} = @{field}"
                )
                parameters.append(
                    bigquery.ScalarQueryParameter(
                        field,
                        "STRING",
                        updates.get(field)
                    )
                )

        array_fields = [
            "selected_columns",
            "business_key"
        ]

        for field in array_fields:
            if field in updates:
                assignments.append(
                    f"{field} = @{field}"
                )
                parameters.append(
                    bigquery.ArrayQueryParameter(
                        field,
                        "STRING",
                        updates.get(field) or []
                    )
                )

        if "rules" in updates:
            assignments.append(
                "draft_rules = PARSE_JSON(@draft_rules)"
            )
            parameters.append(
                bigquery.ScalarQueryParameter(
                    "draft_rules",
                    "STRING",
                    json.dumps(
                        updates.get("rules") or [],
                        ensure_ascii=False
                    )
                )
            )

        if not assignments:
            raise HTTPException(
                status_code=400,
                detail="No se enviaron campos para actualizar"
            )

        assignments.extend([
            "draft_status = 'READY_FOR_VALIDATION'",
            "validation_status = 'PENDING'",
            "validation_message = NULL",
            "updated_at = CURRENT_TIMESTAMP()"
        ])

        query = f"""
        UPDATE
        `{self.project_id}.{self.dataset_id}.data_quality_config_draft`
        SET
          {", ".join(assignments)}
        WHERE draft_id = @draft_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=parameters
        )

        self.client.query(
            query,
            job_config=job_config
        ).result()

        return self.get_draft(draft_id)

    def update_draft_validation(
        self,
        draft_id: str,
        draft_status: str,
        validation_status: str,
        validation_message: str
    ) -> None:
        query = f"""
        UPDATE
        `{self.project_id}.{self.dataset_id}.data_quality_config_draft`
        SET
          draft_status = @draft_status,
          validation_status = @validation_status,
          validation_message = @validation_message,
          updated_at = CURRENT_TIMESTAMP()
        WHERE draft_id = @draft_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "draft_status",
                    "STRING",
                    draft_status
                ),
                bigquery.ScalarQueryParameter(
                    "validation_status",
                    "STRING",
                    validation_status
                ),
                bigquery.ScalarQueryParameter(
                    "validation_message",
                    "STRING",
                    validation_message
                ),
                bigquery.ScalarQueryParameter(
                    "draft_id",
                    "STRING",
                    draft_id
                )
            ]
        )

        self.client.query(
            query,
            job_config=job_config
        ).result()

    def create_confirmed_config(
        self,
        quality_config_id: str,
        draft: dict,
        connection: dict,
        confirmed_by: str,
        active_flag: bool
    ) -> None:
        query = f"""
        INSERT INTO
        `{self.project_id}.{self.dataset_id}.data_quality_config`
        (
          quality_config_id,
          config_name,
          domain_name,
          description,

          connection_id,
          project_id,
          dataset_id,
          table_id,

          selected_columns,
          business_key,
          date_column,
          table_filter,

          related_reconciliation_id,

          configuration_mode,
          active_flag,
          owner_email,

          schedule_enabled,
          schedule_cron,
          schedule_timezone,

          validation_status,
          confirmed_by,
          confirmed_at,

          created_at,
          updated_at
        )
        VALUES
        (
          @quality_config_id,
          @config_name,
          @domain_name,
          @description,

          @connection_id,
          @project_id,
          @dataset_id,
          @table_id,

          @selected_columns,
          @business_key,
          @date_column,
          @table_filter,

          @related_reconciliation_id,

          'AGENT_ASSISTED',
          @active_flag,
          @owner_email,

          FALSE,
          NULL,
          NULL,

          'VALIDATED',
          @confirmed_by,
          CURRENT_TIMESTAMP(),

          CURRENT_TIMESTAMP(),
          CURRENT_TIMESTAMP()
        )
        """

        parameters = [
            bigquery.ScalarQueryParameter(
                "quality_config_id",
                "STRING",
                quality_config_id
            ),
            bigquery.ScalarQueryParameter(
                "config_name",
                "STRING",
                draft.get("config_name")
            ),
            bigquery.ScalarQueryParameter(
                "domain_name",
                "STRING",
                draft.get("domain_name")
            ),
            bigquery.ScalarQueryParameter(
                "description",
                "STRING",
                draft.get("description")
            ),
            bigquery.ScalarQueryParameter(
                "connection_id",
                "STRING",
                draft.get("connection_id")
            ),
            bigquery.ScalarQueryParameter(
                "project_id",
                "STRING",
                connection.get("project_id")
            ),
            bigquery.ScalarQueryParameter(
                "dataset_id",
                "STRING",
                draft.get("dataset_id")
            ),
            bigquery.ScalarQueryParameter(
                "table_id",
                "STRING",
                draft.get("table_id")
            ),
            bigquery.ArrayQueryParameter(
                "selected_columns",
                "STRING",
                draft.get("selected_columns") or []
            ),
            bigquery.ArrayQueryParameter(
                "business_key",
                "STRING",
                draft.get("business_key") or []
            ),
            bigquery.ScalarQueryParameter(
                "date_column",
                "STRING",
                draft.get("date_column")
            ),
            bigquery.ScalarQueryParameter(
                "table_filter",
                "STRING",
                draft.get("table_filter")
            ),
            bigquery.ScalarQueryParameter(
                "related_reconciliation_id",
                "STRING",
                draft.get("related_reconciliation_id")
            ),
            bigquery.ScalarQueryParameter(
                "active_flag",
                "BOOL",
                active_flag
            ),
            bigquery.ScalarQueryParameter(
                "owner_email",
                "STRING",
                draft.get("user_email")
            ),
            bigquery.ScalarQueryParameter(
                "confirmed_by",
                "STRING",
                confirmed_by
            )
        ]

        job_config = bigquery.QueryJobConfig(
            query_parameters=parameters
        )

        self.client.query(
            query,
            job_config=job_config
        ).result()

    def create_rules(
        self,
        quality_config_id: str,
        rules: list[dict]
    ) -> None:
        for index, rule in enumerate(
            rules,
            start=1
        ):
            rule_id = (
                f"RULE_{quality_config_id}_{index:03d}"
            )

            query = f"""
            INSERT INTO
            `{self.project_id}.{self.dataset_id}.data_quality_rule`
            (
              rule_id,
              quality_config_id,

              rule_name,
              rule_dimension,
              rule_type,

              column_name,
              comparison_column,

              rule_parameters,

              warning_threshold,
              critical_threshold,

              severity_level,
              active_flag,

              created_at,
              updated_at
            )
            VALUES
            (
              @rule_id,
              @quality_config_id,

              @rule_name,
              @rule_dimension,
              @rule_type,

              @column_name,
              @comparison_column,

              PARSE_JSON(@rule_parameters),

              @warning_threshold,
              @critical_threshold,

              @severity_level,
              @active_flag,

              CURRENT_TIMESTAMP(),
              CURRENT_TIMESTAMP()
            )
            """

            parameters = [
                bigquery.ScalarQueryParameter(
                    "rule_id",
                    "STRING",
                    rule_id
                ),
                bigquery.ScalarQueryParameter(
                    "quality_config_id",
                    "STRING",
                    quality_config_id
                ),
                bigquery.ScalarQueryParameter(
                    "rule_name",
                    "STRING",
                    rule.get("rule_name")
                ),
                bigquery.ScalarQueryParameter(
                    "rule_dimension",
                    "STRING",
                    rule.get("rule_dimension")
                ),
                bigquery.ScalarQueryParameter(
                    "rule_type",
                    "STRING",
                    rule.get("rule_type")
                ),
                bigquery.ScalarQueryParameter(
                    "column_name",
                    "STRING",
                    rule.get("column_name")
                ),
                bigquery.ScalarQueryParameter(
                    "comparison_column",
                    "STRING",
                    rule.get("comparison_column")
                ),
                bigquery.ScalarQueryParameter(
                    "rule_parameters",
                    "STRING",
                    json.dumps(
                        rule.get("rule_parameters") or {},
                        ensure_ascii=False
                    )
                ),
                bigquery.ScalarQueryParameter(
                    "warning_threshold",
                    "FLOAT64",
                    rule.get("warning_threshold", 1.0)
                ),
                bigquery.ScalarQueryParameter(
                    "critical_threshold",
                    "FLOAT64",
                    rule.get("critical_threshold", 5.0)
                ),
                bigquery.ScalarQueryParameter(
                    "severity_level",
                    "STRING",
                    rule.get("severity_level", "MEDIUM")
                ),
                bigquery.ScalarQueryParameter(
                    "active_flag",
                    "BOOL",
                    rule.get("active_flag", True)
                )
            ]

            job_config = bigquery.QueryJobConfig(
                query_parameters=parameters
            )

            self.client.query(
                query,
                job_config=job_config
            ).result()

    def confirm_draft(
        self,
        draft_id: str,
        quality_config_id: str
    ) -> None:
        query = f"""
        UPDATE
        `{self.project_id}.{self.dataset_id}.data_quality_config_draft`
        SET
          draft_status = 'CONFIRMED',
          validation_status = 'VALIDATED',
          validation_message = @validation_message,
          updated_at = CURRENT_TIMESTAMP()
        WHERE draft_id = @draft_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "validation_message",
                    "STRING",
                    (
                        "Configuración creada: "
                        f"{quality_config_id}"
                    )
                ),
                bigquery.ScalarQueryParameter(
                    "draft_id",
                    "STRING",
                    draft_id
                )
            ]
        )

        self.client.query(
            query,
            job_config=job_config
        ).result()
