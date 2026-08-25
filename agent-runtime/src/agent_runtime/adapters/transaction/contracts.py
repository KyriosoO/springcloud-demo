from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSort:
    field: Literal["trans_id", "trans_type", "amount"]
    direction: Literal["ASC", "DESC"]


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchInput:
    trans_id: str | None = None
    trans_type: str | None = None
    trans_type_contains: str | None = None
    amount: Decimal | None = None
    amount_gt: Decimal | None = None
    amount_lt: Decimal | None = None
    size: int | None = None
    sorts: tuple[TransactionSort, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchCondition:
    trans_id: str | None
    trans_type: str | None
    trans_type_contains: str | None
    amount: Decimal | None
    amount_gt: Decimal | None
    amount_lt: Decimal | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchWireRequest:
    condition: TransactionSearchCondition
    sorts: tuple[TransactionSort, ...]
    page: Literal[1]
    size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionRecord:
    trans_id: str
    trans_type: str
    amount: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchWireResponse:
    rows: tuple[TransactionRecord, ...]
    total: int
    total_exact: bool
    page: int
    size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListFilter:
    field: str
    operator: str
    value: str | Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListSort:
    field: str
    direction: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListSearchInput:
    filters: tuple[TransactionListFilter, ...]
    page: int
    size: int
    sorts: tuple[TransactionListSort, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListSearchCondition:
    trans_id: str | None = None
    trans_type: str | None = None
    trans_type_contains: str | None = None
    trans_date: datetime | None = None
    trans_date_gt: datetime | None = None
    trans_date_lt: datetime | None = None
    amount: Decimal | None = None
    amount_gt: Decimal | None = None
    amount_lt: Decimal | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListSearchWireRequest:
    condition: TransactionListSearchCondition
    sorts: tuple[TransactionListSort, ...]
    page: int
    size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListRecord:
    trans_id: str
    trans_type: str
    trans_date: datetime | None
    amount: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionListSearchWireResponse:
    rows: tuple[TransactionListRecord, ...]
    total: int
    total_exact: bool
    page: int
    size: int
