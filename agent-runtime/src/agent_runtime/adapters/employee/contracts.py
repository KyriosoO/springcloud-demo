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

