from __future__ import annotations

import re
from typing import Any

from google.cloud import bigquery


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,1023}$")
BQ = chr(96)


def _identifier(value: str, field: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} contiene un identificador no permitido")
    return value


class BigQueryTableProfiler:
    def __init__(self, client: bigquery.Client | None = None) -> None:
        self.client = client or bigquery.Client()

    def profile(self, project_id: str, dataset_id: str, table_id: str) -> dict[str, Any]:
        project = _identifier(project_id, "project_id")
        dataset = _identifier(dataset_id, "dataset_id")
        table = _identifier(table_id, "table_id")
        qualified = f"{project}.{dataset}.{table}"
        table_ref = self.client.get_table(qualified)

        columns = [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description,
            }
            for field in table_ref.schema
        ]
        scalar_columns = [
            field
            for field in table_ref.schema
            if field.field_type not in {"RECORD", "STRUCT", "GEOGRAPHY", "JSON"}
        ]
        select_parts = ["COUNT(*) AS row_count"]
        for field in scalar_columns:
            name = field.name.replace(BQ, "")
            quoted = f"{BQ}{name}{BQ}"
            select_parts.append(
                f"COUNTIF({quoted} IS NULL) AS {BQ}{name}__nulls{BQ}"
            )
            select_parts.append(
                f"APPROX_COUNT_DISTINCT({quoted}) AS {BQ}{name}__distinct{BQ}"
            )

        query = (
            "SELECT\n  "
            + ",\n  ".join(select_parts)
            + f"\nFROM {BQ}{qualified}{BQ}"
        )
        row = next(iter(self.client.query(query).result()))
        metrics = dict(row.items())
        row_count = int(metrics.pop("row_count", 0) or 0)

        for column in columns:
            name = column["name"]
            normalized = name.lower()
            column["null_count"] = int(metrics.get(f"{name}__nulls", 0) or 0)
            column["distinct_count"] = int(
                metrics.get(f"{name}__distinct", 0) or 0
            )
            column["null_ratio"] = (
                column["null_count"] / row_count if row_count else 0.0
            )
            column["unique_ratio"] = (
                column["distinct_count"] / row_count if row_count else 0.0
            )
            column["critical_candidate"] = (
                column["mode"] == "REQUIRED"
                or normalized == "id"
                or normalized.endswith("_id")
                or normalized.endswith("_key")
                or normalized.endswith("_codigo")
            )
            column["business_key_candidate"] = bool(
                row_count
                and column["null_count"] == 0
                and column["distinct_count"] == row_count
                and column["critical_candidate"]
            )

        return {
            "table": qualified,
            "row_count": row_count,
            "columns": columns,
            "business_key_candidates": [
                column["name"]
                for column in columns
                if column["business_key_candidate"]
            ],
            "critical_columns": [
                column["name"]
                for column in columns
                if column["critical_candidate"]
            ],
            "partitioning": (
                table_ref.time_partitioning.field
                if table_ref.time_partitioning
                else None
            ),
            "clustering_fields": list(table_ref.clustering_fields or []),
        }
