from typing import Any, Optional

from pydantic import BaseModel, Field


class DataQualityDraftRequest(BaseModel):
    config_name: str
    domain_name: Optional[str] = None
    description: Optional[str] = None

    connection_id: str
    dataset_id: str
    table_id: str

    selected_columns: list[str] = Field(default_factory=list)
    business_key: list[str] = Field(default_factory=list)
    date_column: Optional[str] = None
    table_filter: Optional[str] = None

    related_reconciliation_id: Optional[str] = None

    requested_by: str = "system"
    session_id: Optional[str] = None


class DataQualityProfileRequest(BaseModel):
    connection_id: str
    dataset_id: str
    table_id: str
    selected_columns: list[str] = Field(default_factory=list)
    sample_limit: Optional[int] = None


class DataQualityRuleDraft(BaseModel):
    rule_name: str
    rule_dimension: str
    rule_type: str

    column_name: Optional[str] = None
    comparison_column: Optional[str] = None

    rule_parameters: dict[str, Any] = Field(default_factory=dict)

    warning_threshold: float = 1.0
    critical_threshold: float = 5.0

    severity_level: str = "MEDIUM"
    active_flag: bool = True
