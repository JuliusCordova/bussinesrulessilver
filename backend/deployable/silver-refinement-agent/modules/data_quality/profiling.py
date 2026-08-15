import re

from fastapi import HTTPException
from google.cloud import bigquery


NUMERIC_TYPES = {
    "INTEGER",
    "INT64",
    "FLOAT",
    "FLOAT64",
    "NUMERIC",
    "BIGNUMERIC",
    "DECIMAL"
}


def validate_identifier(
    value: str,
    field_name: str
) -> str:
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} es obligatorio"
        )

    if not re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        raise HTTPException(
            status_code=400,
            detail=f"Identificador inválido: {field_name}"
        )

    return value


class DataProfiler:

    def __init__(
        self,
        client: bigquery.Client
    ):
        self.client = client

    def profile_table(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        selected_columns: list[str] | None = None
    ) -> dict:
        project_id = validate_identifier(
            project_id,
            "project_id"
        )
        dataset_id = validate_identifier(
            dataset_id,
            "dataset_id"
        )
        table_id = validate_identifier(
            table_id,
            "table_id"
        )

        table_ref = (
            f"{project_id}.{dataset_id}.{table_id}"
        )

        table = self.client.get_table(table_ref)

        schema = {
            field.name: field.field_type
            for field in table.schema
        }

        columns = selected_columns or list(schema.keys())

        unknown_columns = [
            column
            for column in columns
            if column not in schema
        ]

        if unknown_columns:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Existen columnas inválidas",
                    "columns": unknown_columns
                }
            )

        column_expressions = []

        for column in columns:
            data_type = schema[column]

            column_expressions.extend([
                (
                    f"COUNTIF(`{column}` IS NULL) "
                    f"AS `{column}__null_count`"
                ),
                (
                    f"COUNT(DISTINCT `{column}`) "
                    f"AS `{column}__distinct_count`"
                )
            ])

            if data_type in NUMERIC_TYPES:
                column_expressions.extend([
                    (
                        f"MIN(`{column}`) "
                        f"AS `{column}__min_value`"
                    ),
                    (
                        f"MAX(`{column}`) "
                        f"AS `{column}__max_value`"
                    ),
                    (
                        f"AVG(CAST(`{column}` AS FLOAT64)) "
                        f"AS `{column}__average_value`"
                    ),
                    (
                        f"STDDEV_POP(CAST(`{column}` AS FLOAT64)) "
                        f"AS `{column}__stddev_value`"
                    )
                ])

        query = f"""
        SELECT
          COUNT(*) AS row_count,
          {", ".join(column_expressions)}
        FROM `{table_ref}`
        """

        rows = list(
            self.client.query(query).result()
        )

        if not rows:
            raise HTTPException(
                status_code=500,
                detail="No se pudo obtener el perfil"
            )

        result = dict(rows[0].items())
        row_count = result.get("row_count", 0)

        profiles = []

        for column in columns:
            null_count = (
                result.get(f"{column}__null_count")
                or 0
            )

            distinct_count = (
                result.get(f"{column}__distinct_count")
                or 0
            )

            profiles.append({
                "column_name": column,
                "data_type": schema[column],
                "row_count": row_count,
                "null_count": null_count,
                "null_percentage": (
                    round(
                        null_count * 100 / row_count,
                        4
                    )
                    if row_count
                    else 0
                ),
                "distinct_count": distinct_count,
                "distinct_percentage": (
                    round(
                        distinct_count * 100 / row_count,
                        4
                    )
                    if row_count
                    else 0
                ),
                "min_value": result.get(
                    f"{column}__min_value"
                ),
                "max_value": result.get(
                    f"{column}__max_value"
                ),
                "average_value": result.get(
                    f"{column}__average_value"
                ),
                "standard_deviation": result.get(
                    f"{column}__stddev_value"
                )
            })

        return {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "table_id": table_id,
            "row_count": row_count,
            "column_profiles": profiles
        }
