from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_runtime.capability_api.contracts import CapabilityStatus, FailureSource

_PRINTABLE_ASCII = re.compile(r"[\x20-\x7e]+")
_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")
_FAILURE_CODE = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")


class StrictTransportModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=False,
        frozen=True,
    )


class RuntimeSubject(StrictTransportModel):
    id: str
    type: Literal["user"]

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value or len(value.encode("utf-8")) > 256:
            raise ValueError("runtime.subject_invalid")
        return value


class RuntimeInvokeRequest(StrictTransportModel):
    contract_version: int = Field(alias="contractVersion")
    request_id: str = Field(alias="requestId")
    correlation_id: str = Field(alias="correlationId")
    question: str
    subject: RuntimeSubject
    deadline_epoch_ms: int = Field(alias="deadlineEpochMs")
    remaining_timeout_ms: int = Field(alias="remainingTimeoutMs")

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("runtime.contract_version_invalid")
        return value

    @field_validator("request_id", "correlation_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not 1 <= len(value) <= 128 or _PRINTABLE_ASCII.fullmatch(value) is None:
            raise ValueError("runtime.identifier_invalid")
        return value

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value or not value.strip() or len(value) > 4096:
            raise ValueError("runtime.question_invalid")
        return value

    @field_validator("deadline_epoch_ms")
    @classmethod
    def validate_deadline(cls, value: int) -> int:
        if value < 1:
            raise ValueError("runtime.deadline_invalid")
        return value

    @field_validator("remaining_timeout_ms")
    @classmethod
    def validate_remaining_timeout(cls, value: int) -> int:
        if not 1 <= value <= 120000:
            raise ValueError("runtime.remaining_timeout_invalid")
        return value


class FailureResponse(StrictTransportModel):
    code: str
    source: FailureSource

    @field_validator("source", mode="before")
    @classmethod
    def parse_source(cls, value: object) -> FailureSource:
        if isinstance(value, FailureSource):
            return value
        if isinstance(value, str):
            return FailureSource(value)
        raise ValueError("runtime.failure_source_invalid")

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not 3 <= len(value) <= 128 or _FAILURE_CODE.fullmatch(value) is None:
            raise ValueError("runtime.failure_code_invalid")
        return value


class RuntimeInvokeResponse(StrictTransportModel):
    contract_version: int = Field(alias="contractVersion")
    request_id: str = Field(alias="requestId")
    status: CapabilityStatus
    capability_id: str | None = Field(alias="capabilityId")
    answer_text: str | None = Field(alias="answerText")
    user_result: dict[str, Any] | None = Field(alias="userResult")
    failure: FailureResponse | None

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, value: object) -> CapabilityStatus:
        if isinstance(value, CapabilityStatus):
            return value
        if isinstance(value, str):
            return CapabilityStatus(value)
        raise ValueError("runtime.status_invalid")

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("runtime.contract_version_invalid")
        return value

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if not 1 <= len(value) <= 128:
            raise ValueError("runtime.request_id_invalid")
        return value

    @field_validator("capability_id")
    @classmethod
    def validate_capability_id(cls, value: str | None) -> str | None:
        if value is not None and (
            not 3 <= len(value) <= 80 or _CAPABILITY_ID.fullmatch(value) is None
        ):
            raise ValueError("runtime.capability_id_invalid")
        return value

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.status in (CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT):
            if self.failure is not None:
                raise ValueError("runtime.response_semantics_invalid")
        elif self.failure is None or self.user_result is not None:
            raise ValueError("runtime.response_semantics_invalid")
        return self


class RuntimeProtocolError(StrictTransportModel):
    contract_version: Literal[1] = Field(alias="contractVersion")
    code: Literal["runtime.protocol_error", "runtime.internal_error"]
