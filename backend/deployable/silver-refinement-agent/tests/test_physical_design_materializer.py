from types import SimpleNamespace

import pytest

from modules.silver_execution.physical_design_materializer import (
    PhysicalDesignMaterializer,
)
from modules.silver_intelligent_mapping.models import PhysicalDesign


def _table(clustering_fields):
    return SimpleNamespace(
        time_partitioning=None,
        clustering_fields=clustering_fields,
    )


def _design(clustering_columns):
    return PhysicalDesign.model_validate(
        {
            "partitioning": {"enabled": False},
            "clustering_columns": clustering_columns,
        }
    )


def test_accepts_existing_clustering_superset_with_expected_prefix():
    service = PhysicalDesignMaterializer.__new__(PhysicalDesignMaterializer)

    service._validate(
        table=_table(
            [
                "producto_id",
                "ramo_id",
                "bronze_registro_id",
                "bronze_carga_id",
            ]
        ),
        target_table="project.silver.cat_producto",
        design=_design(["producto_id"]),
    )


def test_rejects_existing_clustering_when_expected_order_is_not_prefix():
    service = PhysicalDesignMaterializer.__new__(PhysicalDesignMaterializer)

    with pytest.raises(ValueError, match="Physical design mismatch"):
        service._validate(
            table=_table(["ramo_id", "producto_id"]),
            target_table="project.silver.cat_producto",
            design=_design(["producto_id"]),
        )


def test_rejects_missing_expected_clustering_column():
    service = PhysicalDesignMaterializer.__new__(PhysicalDesignMaterializer)

    with pytest.raises(ValueError, match="Physical design mismatch"):
        service._validate(
            table=_table(["producto_id"]),
            target_table="project.silver.cat_producto",
            design=_design(["producto_id", "ramo_id"]),
        )
