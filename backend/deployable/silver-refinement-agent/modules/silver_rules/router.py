from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .srl import compile_srl, parse_srl


router = APIRouter(prefix="/silver-rules", tags=["silver-rules"])


class SrlValidationRequest(BaseModel):
    srl: str = Field(min_length=1, max_length=8000)
    schema: list[dict[str, Any]] = Field(min_length=1)


class SrlValidationResponse(BaseModel):
    valid: bool
    srl: str
    ast: dict[str, Any]
    compiled: dict[str, Any]


@router.post("/validate", response_model=SrlValidationResponse)
def validate_rule(request: SrlValidationRequest) -> SrlValidationResponse:
    try:
        rule = parse_srl(request.srl)
        compiled = compile_srl(rule, request.schema)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return SrlValidationResponse(
        valid=True,
        srl=rule.source_text,
        ast=rule.model_dump(mode="json"),
        compiled=compiled,
    )
