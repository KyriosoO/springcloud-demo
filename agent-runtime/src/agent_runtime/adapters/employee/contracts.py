from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailInput:
    employee_identifier: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailWireRequest:
    employee_identifier: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailWireResponse:
    id_card_no: str
    member_no: str | None
    chinese_name: str
    public_email: str | None
    position: str | None
    work_base_si: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailRecord:
    id_card_no: str
    member_no: str | None
    chinese_name: str
    public_email: str | None
    position: str | None
    work_base_si: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchFilter:
    field: str
    operator: str
    value: str | tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchSort:
    field: str
    direction: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchInput:
    filters: tuple[EmployeeSearchFilter, ...]
    page: int
    size: int
    sorts: tuple[EmployeeSearchSort, ...]
    keyword: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchWireFilter:
    field: str
    operator: str
    value: str | None = None
    values: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchWireRequest:
    filters: tuple[EmployeeSearchWireFilter, ...]
    from_index: int
    size: int
    sorts: tuple[EmployeeSearchSort, ...]
    keyword: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchRecord:
    employee_identifier: str
    chinese_name: str
    contact_address: str | None = None
    member_no: str | None = None
    phone_no: str | None = None
    email: str | None = None
    position: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSearchWireResponse:
    rows: tuple[EmployeeSearchRecord, ...]
    total: int
    total_exact: bool
    from_index: int
    size: int
    upstream_hit_count: int
    allow_partial_page: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSemanticSearchInput:
    query: str
    size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSemanticSearchWireRequest:
    query: str
    size: int
    embedding_field: str
    embedding_dims: int
    num_candidates: int
    track_total_hits: int
