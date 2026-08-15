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
