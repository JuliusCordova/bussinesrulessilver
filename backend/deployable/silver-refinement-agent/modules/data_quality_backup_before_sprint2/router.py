from fastapi import APIRouter, HTTPException
from google.cloud import bigquery

from .models import DataQualityProfileRequest
from .profiling import DataProfiler
from .repository import DataQualityRepository


def create_data_quality_router(
    bq_client: bigquery.Client,
    project_id: str,
    control_dataset: str,
    get_connection_function
) -> APIRouter:
    router = APIRouter(
        prefix="/data-quality",
        tags=["Data Quality"]
    )

    repository = DataQualityRepository(
        client=bq_client,
        project_id=project_id,
        dataset_id=control_dataset
    )

    profiler = DataProfiler(
        client=bq_client
    )

    @router.get("/health")
    def data_quality_health():
        return {
            "status": "ok",
            "module": "data-quality"
        }

    @router.get("/rule-types")
    def list_rule_types():
        return {
            "rule_types": repository.list_rule_types()
        }

    @router.get("/configs")
    def list_configs(
        active_only: bool = True
    ):
        configurations = (
            repository.list_quality_configs(
                active_only=active_only
            )
        )

        return {
            "total": len(configurations),
            "configurations": configurations
        }

    @router.post("/profile")
    def profile_table(
        req: DataQualityProfileRequest
    ):
        connection = get_connection_function(
            req.connection_id
        )

        if (
            connection.get("connection_type")
            != "BIGQUERY"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "El Sprint 1 solo soporta "
                    "conexiones BIGQUERY"
                )
            )

        return profiler.profile_table(
            project_id=connection["project_id"],
            dataset_id=req.dataset_id,
            table_id=req.table_id,
            selected_columns=req.selected_columns
        )

    return router
