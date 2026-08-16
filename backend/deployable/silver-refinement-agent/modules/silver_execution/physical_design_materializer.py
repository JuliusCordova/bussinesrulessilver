from __future__ import annotations

from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from modules.silver_intelligent_mapping.models import PhysicalDesign


class PhysicalDesignMaterializer:
    """Creates a Silver target from governed DDL and rejects physical drift."""

    def __init__(
        self,
        client: bigquery.Client | None = None,
    ) -> None:
        self.client = client or bigquery.Client()

    @staticmethod
    def _enum_value(value: Any) -> str:
        raw = getattr(value, "value", value)
        return str(raw).upper()

    def ensure(
        self,
        *,
        ddl: str,
        target_table: str,
        physical_design: dict,
    ) -> bool:
        design = PhysicalDesign.model_validate(
            physical_design or {}
        )

        created = False

        try:
            table = self.client.get_table(target_table)
        except NotFound:
            self.client.query(ddl).result()
            table = self.client.get_table(target_table)
            created = True

        self._validate(
            table=table,
            target_table=target_table,
            design=design,
        )

        return created

    def _validate(
        self,
        *,
        table,
        target_table: str,
        design: PhysicalDesign,
    ) -> None:
        expected_partition = design.partitioning
        actual_partition = table.time_partitioning

        if expected_partition.enabled:
            if actual_partition is None:
                raise ValueError(
                    f"Physical design mismatch para {target_table}: "
                    "se esperaba tabla particionada"
                )

            if actual_partition.field != expected_partition.column:
                raise ValueError(
                    f"Physical design mismatch para {target_table}: "
                    f"partition field actual={actual_partition.field}, "
                    f"esperado={expected_partition.column}"
                )

            actual_type = self._enum_value(
                actual_partition.type_
            )
            expected_type = (
                expected_partition.granularity.value
            )

            if actual_type != expected_type:
                raise ValueError(
                    f"Physical design mismatch para {target_table}: "
                    f"partition type actual={actual_type}, "
                    f"esperado={expected_type}"
                )

        elif actual_partition is not None:
            raise ValueError(
                f"Physical design mismatch para {target_table}: "
                "la especificación no define particionamiento"
            )

        actual_clusters = list(
            table.clustering_fields or []
        )
        expected_clusters = list(
            design.clustering_columns
        )

        # BigQuery allows up to four clustering columns. An existing target
        # with the governed columns as an ordered prefix is compatible: the
        # additional columns refine clustering without changing the requested
        # leading clustering semantics. Reordering or missing expected columns
        # remains physical drift.
        compatible_clusters = (
            actual_clusters[: len(expected_clusters)]
            == expected_clusters
        )

        if not compatible_clusters:
            raise ValueError(
                f"Physical design mismatch para {target_table}: "
                f"clustering actual={actual_clusters}, "
                f"esperado={expected_clusters}"
            )
