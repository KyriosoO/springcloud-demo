from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Generic, Protocol, TypeVar

from agent_runtime.capability_api.contracts import (
    JsonObject,
    canonical_json_bytes,
    freeze_json_object,
    validate_argument_schema,
)


_ASCII_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_TOOL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")


class QuestionDataClass(StrEnum):
    PUBLIC_KNOWLEDGE = "public_knowledge"
    GENERIC_BUSINESS = "generic_business"
    PERSONAL_IDENTIFIER = "personal_identifier"
    EMPLOYEE_IDENTIFIER = "employee_identifier"
    TRANSACTION_IDENTIFIER = "transaction_identifier"
    FINANCIAL_ACCOUNT = "financial_account"
    CONTACT = "contact"
    CREDENTIAL_OR_SECRET = "credential_or_secret"
    INSTRUCTION_INJECTION = "instruction_injection"
    FREE_TEXT_SENSITIVE = "free_text_sensitive"
    UNKNOWN = "unknown"


class QuestionEgressDisposition(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class QuestionEgressReasonCode(StrEnum):
    INVALID_QUESTION = "invalid_question"
    SENSITIVE_INPUT = "sensitive_input"
    UNKNOWN_INPUT = "unknown_input"


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionEgressDecision:
    disposition: QuestionEgressDisposition
    policy_version: str
    minimized_question: str | None = None
    reason_code: QuestionEgressReasonCode | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.disposition, QuestionEgressDisposition)
            or not isinstance(self.policy_version, str)
            or not self.policy_version
            or len(self.policy_version) > 64
            or not self.policy_version.isascii()
        ):
            raise ValueError("model.invalid_question_egress_decision")
        valid = (
            self.disposition is QuestionEgressDisposition.ALLOWED
            and isinstance(self.minimized_question, str)
            and bool(self.minimized_question)
            and self.reason_code is None
        ) or (
            self.disposition is QuestionEgressDisposition.DENIED
            and self.minimized_question is None
            and isinstance(self.reason_code, QuestionEgressReasonCode)
        )
        if not valid:
            raise ValueError("model.invalid_question_egress_decision")


class ModelTaskId(StrEnum):
    ACTION_SELECTION = "action_selection"
    ANSWER_GENERATION = "answer_generation"
    KNOWLEDGE_REWRITE = "knowledge_rewrite"
    KNOWLEDGE_SUMMARY = "knowledge_summary"


class StructuredToolMode(StrEnum):
    NONE = "none"
    REQUIRED = "required"


class StructuredOutputMode(StrEnum):
    TOOL_CALLS = "tool_calls"
    JSON_OBJECT = "json_object"


class StructuredFinishKind(StrEnum):
    TOOL_CALLS = "tool_calls"
    STOP = "stop"


class ModelProviderFailureKind(StrEnum):
    INPUT_DENIED = "input_denied"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_FAILURE = "provider_failure"
    INVALID_OUTPUT = "invalid_output"


class GroundingRejectionReason(StrEnum):
    CAPABILITY_MISMATCH = "capability_mismatch"
    INVALID_PAYLOAD = "invalid_payload"
    UNKNOWN_FACT = "unknown_fact"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    DOMAIN_POLICY_REJECTED = "domain_policy_rejected"


class ModelBoundaryError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ModelInputDenied(ModelBoundaryError):
    pass


class InvalidModelOutput(ModelBoundaryError):
    pass


class MissingGroundingPolicy(ModelBoundaryError):
    pass


class MissingModelCallContext(ModelBoundaryError):
    pass


class ModelTransportError(RuntimeError):
    __slots__ = ("kind",)

    def __init__(self, kind: ModelProviderFailureKind) -> None:
        super().__init__(kind.value)
        self.kind = kind


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCallContext:
    request_id: str
    correlation_id: str
    deadline_monotonic: float

    def __post_init__(self) -> None:
        for value in (self.request_id, self.correlation_id):
            if not isinstance(value, str) or not value or len(value) > 128 or not value.isascii() or not value.isprintable():
                raise ValueError("model.invalid_call_context")
        if (
            not isinstance(self.deadline_monotonic, (int, float))
            or isinstance(self.deadline_monotonic, bool)
            or not math.isfinite(self.deadline_monotonic)
        ):
            raise ValueError("model.invalid_call_context")


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredToolDefinition:
    name: str
    description: str
    arguments_schema: JsonObject

    def __post_init__(self) -> None:
        if not _TOOL_NAME.fullmatch(self.name):
            raise ModelInputDenied("model.invalid_tool_definition")
        if not isinstance(self.description, str) or not self.description or len(self.description) > 1024:
            raise ModelInputDenied("model.invalid_tool_definition")
        try:
            schema = freeze_json_object(
                self.arguments_schema,
                max_bytes=32768,
                max_depth=16,
                max_collection_items=2048,
            )
            validate_argument_schema(schema)
        except ValueError as exc:
            raise ModelInputDenied("model.invalid_tool_definition") from exc
        object.__setattr__(self, "arguments_schema", schema)


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredModelRequest:
    task_id: ModelTaskId
    task_version: str
    system_instruction: str
    user_payload_json: str
    tools: tuple[StructuredToolDefinition, ...]
    tool_mode: StructuredToolMode
    output_mode: StructuredOutputMode
    max_output_tokens: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))
        if not isinstance(self.task_id, ModelTaskId):
            raise ModelInputDenied("model.invalid_request")
        if not isinstance(self.task_version, str) or not self.task_version or len(self.task_version) > 64:
            raise ModelInputDenied("model.invalid_request")
        if (
            not isinstance(self.system_instruction, str)
            or not self.system_instruction
            or len(self.system_instruction.encode("utf-8")) > 8192
        ):
            raise ModelInputDenied("model.invalid_request")
        if not isinstance(self.user_payload_json, str) or not self.user_payload_json:
            raise ModelInputDenied("model.invalid_request")
        if not isinstance(self.max_output_tokens, int) or isinstance(self.max_output_tokens, bool) or self.max_output_tokens <= 0:
            raise ModelInputDenied("model.invalid_request")
        if any(not isinstance(tool, StructuredToolDefinition) for tool in self.tools):
            raise ModelInputDenied("model.invalid_request")
        if self.tool_mode is StructuredToolMode.REQUIRED:
            if self.output_mode is not StructuredOutputMode.TOOL_CALLS or not self.tools:
                raise ModelInputDenied("model.invalid_request")
        elif self.tool_mode is StructuredToolMode.NONE:
            if self.output_mode is not StructuredOutputMode.JSON_OBJECT or self.tools:
                raise ModelInputDenied("model.invalid_request")
        else:
            raise ModelInputDenied("model.invalid_request")


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredToolCall:
    name: str
    arguments_json: str

    def __post_init__(self) -> None:
        if not _TOOL_NAME.fullmatch(self.name) or not isinstance(self.arguments_json, str):
            raise InvalidModelOutput("model.invalid_tool_call")


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredModelResponse:
    finish_kind: StructuredFinishKind
    content: str | None
    tool_calls: tuple[StructuredToolCall, ...]
    usage_total_tokens: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        if not isinstance(self.finish_kind, StructuredFinishKind):
            raise InvalidModelOutput("model.invalid_response")
        if self.content is not None and not isinstance(self.content, str):
            raise InvalidModelOutput("model.invalid_response")
        if any(not isinstance(tool_call, StructuredToolCall) for tool_call in self.tool_calls):
            raise InvalidModelOutput("model.invalid_response")
        if self.finish_kind is StructuredFinishKind.TOOL_CALLS and not self.tool_calls:
            raise InvalidModelOutput("model.invalid_response")
        if self.finish_kind is StructuredFinishKind.STOP and self.tool_calls:
            raise InvalidModelOutput("model.invalid_response")
        if self.usage_total_tokens is not None and (
            not isinstance(self.usage_total_tokens, int)
            or isinstance(self.usage_total_tokens, bool)
            or self.usage_total_tokens < 0
        ):
            raise InvalidModelOutput("model.invalid_response")


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateAnswer:
    answer: str
    used_fact_ids: tuple[str, ...]
    unsupported_claims: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "used_fact_ids", tuple(self.used_fact_ids))
        object.__setattr__(self, "unsupported_claims", tuple(self.unsupported_claims))
        if not isinstance(self.answer, str) or not self.answer or len(self.answer) > 4096:
            raise InvalidModelOutput("model.invalid_answer")
        if any(ord(character) < 32 or ord(character) == 127 for character in self.answer):
            raise InvalidModelOutput("model.invalid_answer")
        if not 1 <= len(self.used_fact_ids) <= 256 or len(set(self.used_fact_ids)) != len(self.used_fact_ids):
            raise InvalidModelOutput("model.invalid_fact_ids")
        if any(not _ASCII_IDENTIFIER.fullmatch(item) for item in self.used_fact_ids):
            raise InvalidModelOutput("model.invalid_fact_ids")
        if self.unsupported_claims:
            raise InvalidModelOutput("model.unsupported_claims")


@dataclass(frozen=True, slots=True, kw_only=True)
class GroundingInput:
    capability_id: str
    minimized_question: str
    safe_payload: JsonObject
    candidate: CandidateAnswer

    def __post_init__(self) -> None:
        if not _CAPABILITY_ID.fullmatch(self.capability_id):
            raise InvalidModelOutput("model.invalid_grounding_input")
        if not isinstance(self.minimized_question, str) or not self.minimized_question:
            raise InvalidModelOutput("model.invalid_grounding_input")
        object.__setattr__(
            self,
            "safe_payload",
            freeze_json_object(
                self.safe_payload,
                max_bytes=65536,
                max_depth=8,
                max_collection_items=256,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GroundingDecision:
    accepted: bool
    reason: GroundingRejectionReason | None = None

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise ValueError("model.invalid_grounding_decision")
        if self.accepted and self.reason is not None:
            raise ValueError("model.invalid_grounding_decision")
        if not self.accepted and not isinstance(self.reason, GroundingRejectionReason):
            raise ValueError("model.invalid_grounding_decision")


TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")
TOutput_co = TypeVar("TOutput_co", covariant=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelTaskDefinition(Generic[TInput, TOutput]):
    task_id: ModelTaskId
    task_version: str
    input_type: type[TInput]
    max_input_bytes: int
    timeout_ms: int
    max_output_tokens: int
    build_request: Callable[[TInput], StructuredModelRequest]
    parse_response: Callable[[StructuredModelResponse], TOutput]

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, ModelTaskId) or not self.task_version:
            raise ValueError("model.invalid_task_definition")
        for value in (self.max_input_bytes, self.timeout_ms, self.max_output_tokens):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError("model.invalid_task_definition")
        if not isinstance(self.input_type, type) or not callable(self.build_request) or not callable(self.parse_response):
            raise ValueError("model.invalid_task_definition")


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelTaskResult(Generic[TOutput_co]):
    output: TOutput_co | None = None
    failure_kind: ModelProviderFailureKind | None = None

    def __post_init__(self) -> None:
        if (self.output is None) == (self.failure_kind is None):
            raise ValueError("model.invalid_task_result")
        if self.failure_kind is not None and not isinstance(self.failure_kind, ModelProviderFailureKind):
            raise ValueError("model.invalid_task_result")


class StructuredModelGateway(Protocol):
    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[TInput, TOutput],
        input: TInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[TOutput]: ...


class StructuredModelTransport(Protocol):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse: ...


class AnswerGroundingPolicy(Protocol):
    def validate(self, input: GroundingInput) -> GroundingDecision: ...


def canonical_object_json(value: JsonObject) -> str:
    return canonical_json_bytes(value).decode("utf-8")
