from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmployeeField(StrEnum):
    POSITION = "position"
    WORK_BASE_SI = "workBaseSi"


class QueryOperator(StrEnum):
    EQ = "EQ"
    IN = "IN"


class SortDirection(StrEnum):
    ASC = "ASC"
    DESC = "DESC"


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: EmployeeField
    operator: QueryOperator
    values: tuple[str, ...]


class QuerySort(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: Literal[EmployeeField.POSITION]
    direction: SortDirection


class QueryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    number: int = Field(ge=0, le=100)
    size: int = Field(ge=1, le=100)


class EmployeeQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: UUID = Field(alias="requestId")
    filters: tuple[QueryFilter, ...] = Field(max_length=10)
    select: tuple[EmployeeField, ...] = Field(min_length=1, max_length=2)
    sorts: tuple[QuerySort, ...] = Field(max_length=2)
    page: QueryPage
    deadline_at: datetime = Field(alias="deadlineAt")


class EmployeeItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    position: str | None = None
    work_base_si: str | None = Field(default=None, alias="workBaseSi")


class EmployeeQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: UUID = Field(alias="requestId")
    items: tuple[EmployeeItem, ...]
    page: QueryPage
    total: int | None
    observed_at: datetime | None = Field(default=None, alias="observedAt")
    source_version: str | None = Field(alias="sourceVersion")
