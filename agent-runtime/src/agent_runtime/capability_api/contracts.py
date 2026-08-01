from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Generic, Mapping, Protocol, Self, TypeAlias, TypeVar, runtime_checkable

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]

CAPABILITY_API_VERSION = 1

_CAPABILITY_ID_PATTERN = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")
_FAILURE_CODE_PATTERN = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")
_PRINTABLE_ASCII_PATTERN = re.compile(r"[\x20-\x7e]+")
_SCHEMA_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "description",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "items",
    }
)
_SCHEMA_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean"})
_SENSITIVE_DESCRIPTION_MARKERS = (
    "http://",
    "https://",
    "authorization:",
    "bearer ",
    "api_key",
    "apikey",
    "password=",
)


class CapabilityKind(StrEnum):
    QUERY = "query"


class SubjectType(StrEnum):
    USER = "user"


class CapabilityStatus(StrEnum):
    SUCCESS = "success"
    NO_RESULT = "no_result"
    UNSUPPORTED = "unsupported"
    INVALID_ARGUMENT = "invalid_argument"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    DOWNSTREAM_FAILURE = "downstream_failure"
    MODEL_EGRESS_DENIED = "model_egress_denied"
    INTERNAL_FAILURE = "internal_failure"


class EgressDisposition(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    NOT_APPLICABLE = "not_applicable"


class FailureSource(StrEnum):
    CORE = "core"
    CAPABILITY = "capability"
    DOWNSTREAM = "downstream"
    POLICY = "policy"


class CancellationSource(StrEnum):
    CLIENT_DISCONNECT = "client_disconnect"
    UPSTREAM_CANCEL = "upstream_cancel"
    RUNTIME_SHUTDOWN = "runtime_shutdown"


class ContractViolation(ValueError):
    """Raised when a public capability contract is malformed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class InvalidExecutionContext(ContractViolation):
    pass


class InvalidCapabilityArguments(ContractViolation):
    pass


def _validate_json_value(
    value: object,
    *,
    depth: int,
    max_depth: int,
    max_collection_items: int,
) -> JsonValue:
    if depth > max_depth:
        raise ContractViolation("core.json_depth_exceeded")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("core.json_non_finite_number")
        return value
    if isinstance(value, Mapping):
        if len(value) > max_collection_items:
            raise ContractViolation("core.json_collection_too_large")
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractViolation("core.json_object_key_invalid")
            frozen[key] = _validate_json_value(
                item,
                depth=depth + 1,
                max_depth=max_depth,
                max_collection_items=max_collection_items,
            )
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if len(value) > max_collection_items:
            raise ContractViolation("core.json_collection_too_large")
        return tuple(
            _validate_json_value(
                item,
                depth=depth + 1,
                max_depth=max_depth,
                max_collection_items=max_collection_items,
            )
            for item in value
        )
    raise ContractViolation("core.json_type_not_allowed")


def _to_plain_json(value: JsonValue) -> JsonScalar | list[object] | dict[str, object]:
    if isinstance(value, Mapping):
        return {key: _to_plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_plain_json(item) for item in value]
    return value


def canonical_json_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        _to_plain_json(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def freeze_json_object(
    value: object,
    *,
    max_bytes: int,
    max_depth: int,
    max_collection_items: int,
) -> JsonObject:
    frozen = _validate_json_value(
        value,
        depth=1,
        max_depth=max_depth,
        max_collection_items=max_collection_items,
    )
    if not isinstance(frozen, Mapping):
        raise ContractViolation("core.json_object_required")
    if len(canonical_json_bytes(frozen)) > max_bytes:
        raise ContractViolation("core.json_bytes_exceeded")
    return frozen


def _require_non_empty_text(value: object, *, code: str, max_chars: int) -> str:
    if not isinstance(value, str) or not value or not value.strip() or len(value) > max_chars:
        raise ContractViolation(code)
    return value


def _validate_schema_node(node: object) -> None:
    if not isinstance(node, Mapping):
        raise ContractViolation("registry.invalid_argument_schema")
    unknown = set(node) - _SCHEMA_KEYWORDS
    if unknown:
        raise ContractViolation("registry.invalid_argument_schema")
    schema_type = node.get("type")
    if not isinstance(schema_type, str) or schema_type not in _SCHEMA_TYPES:
        raise ContractViolation("registry.invalid_argument_schema")
    additional = node.get("additionalProperties")
    if schema_type == "object" and additional is not False:
        raise ContractViolation("registry.invalid_argument_schema")
    if schema_type != "object" and additional is not None:
        raise ContractViolation("registry.invalid_argument_schema")
    description = node.get("description")
    if description is not None and not isinstance(description, str):
        raise ContractViolation("registry.invalid_argument_schema")

    properties = node.get("properties")
    if properties is not None:
        if schema_type != "object":
            raise ContractViolation("registry.invalid_argument_schema")
        if not isinstance(properties, Mapping) or not all(isinstance(key, str) for key in properties):
            raise ContractViolation("registry.invalid_argument_schema")
        for child in properties.values():
            _validate_schema_node(child)
    items = node.get("items")
    if items is not None:
        if schema_type != "array":
            raise ContractViolation("registry.invalid_argument_schema")
        _validate_schema_node(items)
    elif schema_type == "array":
        raise ContractViolation("registry.invalid_argument_schema")

    required = node.get("required")
    if required is not None:
        if schema_type != "object":
            raise ContractViolation("registry.invalid_argument_schema")
        if not isinstance(required, tuple) or not all(isinstance(item, str) for item in required):
            raise ContractViolation("registry.invalid_argument_schema")
        if len(set(required)) != len(required):
            raise ContractViolation("registry.invalid_argument_schema")
        if properties is not None and not set(required).issubset(properties):
            raise ContractViolation("registry.invalid_argument_schema")
    enum = node.get("enum")
    if enum is not None:
        if not isinstance(enum, tuple) or not enum:
            raise ContractViolation("registry.invalid_argument_schema")
        for item in enum:
            if item is not None and not isinstance(item, (bool, int, float, str)):
                raise ContractViolation("registry.invalid_argument_schema")

    numeric_minimum = node.get("minimum")
    numeric_maximum = node.get("maximum")
    if numeric_minimum is not None or numeric_maximum is not None:
        if schema_type not in ("integer", "number"):
            raise ContractViolation("registry.invalid_argument_schema")
        for value in (numeric_minimum, numeric_maximum):
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
            ):
                raise ContractViolation("registry.invalid_argument_schema")
        if numeric_minimum is not None and numeric_maximum is not None and numeric_minimum > numeric_maximum:
            raise ContractViolation("registry.invalid_argument_schema")

    for minimum_key, maximum_key, owning_type in (
        ("minLength", "maxLength", "string"),
        ("minItems", "maxItems", "array"),
    ):
        minimum = node.get(minimum_key)
        maximum = node.get(maximum_key)
        if minimum is None and maximum is None:
            continue
        if schema_type != owning_type:
            raise ContractViolation("registry.invalid_argument_schema")
        for value in (minimum, maximum):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ContractViolation("registry.invalid_argument_schema")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ContractViolation("registry.invalid_argument_schema")


def validate_argument_schema(schema: JsonObject) -> None:
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise ContractViolation("registry.invalid_argument_schema")
    _validate_schema_node(schema)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityDescriptor:
    capability_id: str
    api_version: int
    kind: CapabilityKind
    display_name: str
    description: str
    aliases: tuple[str, ...]
    argument_schema: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(
            self,
            "argument_schema",
            freeze_json_object(
                self.argument_schema,
                max_bytes=32768,
                max_depth=16,
                max_collection_items=2048,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionCandidate:
    capability_id: str
    arguments: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            freeze_json_object(
                self.arguments,
                max_bytes=65536,
                max_depth=16,
                max_collection_items=2048,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class FailureDetail:
    code: str
    source: FailureSource

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or len(self.code) > 128 or not _FAILURE_CODE_PATTERN.fullmatch(self.code):
            raise ContractViolation("core.invalid_failure_detail")
        if not isinstance(self.source, FailureSource):
            raise ContractViolation("core.invalid_failure_detail")


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelEgressResult:
    disposition: EgressDisposition
    policy_version: str | None = None
    safe_payload: JsonObject | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.safe_payload is not None:
            object.__setattr__(
                self,
                "safe_payload",
                freeze_json_object(
                    self.safe_payload,
                    max_bytes=262144,
                    max_depth=16,
                    max_collection_items=2048,
                ),
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityResult:
    status: CapabilityStatus
    domain_result: JsonObject | None
    egress: ModelEgressResult
    failure: FailureDetail | None

    def __post_init__(self) -> None:
        if self.domain_result is not None:
            object.__setattr__(
                self,
                "domain_result",
                freeze_json_object(
                    self.domain_result,
                    max_bytes=1048576,
                    max_depth=16,
                    max_collection_items=2048,
                ),
            )


class OpaqueUserToken:
    __slots__ = ("_raw",)

    def __init__(self, raw: str) -> None:
        self._raw = raw

    @classmethod
    def from_raw(cls, raw: str) -> Self:
        if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 16384:
            raise InvalidExecutionContext("core.user_identity_required")
        return cls(raw)

    def reveal_for_outbound(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return "<redacted>"

    __str__ = __repr__

    def __hash__(self) -> int:
        raise TypeError("unhashable type: OpaqueUserToken")


@runtime_checkable
class CancellationSignal(Protocol):
    def is_cancelled(self) -> bool: ...

    async def wait_cancelled(self) -> CancellationSource: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityExecutionContext:
    request_id: str
    correlation_id: str
    original_question: str
    subject_id: str
    subject_type: SubjectType
    user_token: OpaqueUserToken
    deadline_monotonic: float
    cancellation: CancellationSignal

    def __post_init__(self) -> None:
        for value in (self.request_id, self.correlation_id):
            if not isinstance(value, str) or len(value) > 128 or not _PRINTABLE_ASCII_PATTERN.fullmatch(value):
                raise InvalidExecutionContext("core.invalid_execution_context")
        _require_non_empty_text(self.original_question, code="core.invalid_question", max_chars=16384)
        if not isinstance(self.subject_id, str) or not self.subject_id or len(self.subject_id.encode("utf-8")) > 256:
            raise InvalidExecutionContext("core.user_identity_required")
        if self.subject_type is not SubjectType.USER or not isinstance(self.user_token, OpaqueUserToken):
            raise InvalidExecutionContext("core.user_identity_required")
        if not isinstance(self.deadline_monotonic, (int, float)) or not math.isfinite(self.deadline_monotonic):
            raise InvalidExecutionContext("core.invalid_execution_context")
        if not isinstance(self.cancellation, CancellationSignal):
            raise InvalidExecutionContext("core.invalid_execution_context")


TInput = TypeVar("TInput")
TValidated_co = TypeVar("TValidated_co", covariant=True)
THandled_contra = TypeVar("THandled_contra", contravariant=True)


class CapabilityArgumentValidator(Protocol[TValidated_co]):
    def validate(self, arguments: JsonObject) -> TValidated_co: ...


class CapabilityHandler(Protocol[THandled_contra]):
    async def handle(self, input: THandled_contra, context: CapabilityExecutionContext) -> CapabilityResult: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityRegistrationCandidate(Generic[TInput]):
    descriptor: CapabilityDescriptor
    enabled: bool
    argument_validator: CapabilityArgumentValidator[TInput] | None
    handler: CapabilityHandler[TInput] | None


class CapabilityRegistrationProvider(Protocol):
    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]: ...


def validate_descriptor(
    descriptor: CapabilityDescriptor,
    *,
    max_bytes: int,
    max_depth: int,
    max_collection_items: int,
) -> CapabilityDescriptor:
    if not isinstance(descriptor, CapabilityDescriptor):
        raise ContractViolation("registry.invalid_descriptor")
    if len(descriptor.capability_id) > 80 or not _CAPABILITY_ID_PATTERN.fullmatch(descriptor.capability_id):
        raise ContractViolation("registry.invalid_descriptor")
    if descriptor.api_version != CAPABILITY_API_VERSION:
        raise ContractViolation("registry.unsupported_api_version")
    if descriptor.kind is not CapabilityKind.QUERY:
        raise ContractViolation("registry.invalid_descriptor")
    _require_non_empty_text(descriptor.display_name, code="registry.invalid_descriptor", max_chars=80)
    _require_non_empty_text(descriptor.description, code="registry.invalid_descriptor", max_chars=512)
    lowered_description = descriptor.description.casefold()
    if any(marker in lowered_description for marker in _SENSITIVE_DESCRIPTION_MARKERS):
        raise ContractViolation("registry.invalid_descriptor")
    if len(descriptor.aliases) > 8:
        raise ContractViolation("registry.invalid_descriptor")
    for alias in descriptor.aliases:
        _require_non_empty_text(alias, code="registry.invalid_descriptor", max_chars=64)
    schema = freeze_json_object(
        descriptor.argument_schema,
        max_bytes=max_bytes,
        max_depth=max_depth,
        max_collection_items=max_collection_items,
    )
    validate_argument_schema(schema)
    normalized = CapabilityDescriptor(
        capability_id=descriptor.capability_id,
        api_version=descriptor.api_version,
        kind=descriptor.kind,
        display_name=descriptor.display_name,
        description=descriptor.description,
        aliases=descriptor.aliases,
        argument_schema=schema,
    )
    if len(canonical_json_bytes(descriptor_to_json(normalized))) > max_bytes:
        raise ContractViolation("registry.invalid_descriptor")
    return normalized


def descriptor_to_json(descriptor: CapabilityDescriptor) -> JsonObject:
    return freeze_json_object(
        {
            "capability_id": descriptor.capability_id,
            "api_version": descriptor.api_version,
            "kind": descriptor.kind.value,
            "display_name": descriptor.display_name,
            "description": descriptor.description,
            "aliases": descriptor.aliases,
            "argument_schema": descriptor.argument_schema,
        },
        max_bytes=131072,
        max_depth=16,
        max_collection_items=2048,
    )


def validate_action_candidate(
    candidate: ActionCandidate,
    *,
    max_argument_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> ActionCandidate:
    if not isinstance(candidate, ActionCandidate):
        raise ContractViolation("core.invalid_candidate")
    if len(candidate.capability_id) > 80 or not _CAPABILITY_ID_PATTERN.fullmatch(candidate.capability_id):
        raise ContractViolation("core.invalid_candidate")
    try:
        arguments = freeze_json_object(
            candidate.arguments,
            max_bytes=max_argument_bytes,
            max_depth=max_json_depth,
            max_collection_items=max_collection_items,
        )
    except ContractViolation as exc:
        raise ContractViolation("core.invalid_candidate") from exc
    return ActionCandidate(capability_id=candidate.capability_id, arguments=arguments)


def validate_capability_result(
    result: CapabilityResult,
    *,
    max_domain_result_bytes: int,
    max_model_payload_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> CapabilityResult:
    if not isinstance(result, CapabilityResult) or not isinstance(result.status, CapabilityStatus):
        raise ContractViolation("core.invalid_result")
    if not isinstance(result.egress, ModelEgressResult) or not isinstance(result.egress.disposition, EgressDisposition):
        raise ContractViolation("core.invalid_result")

    domain_result = None
    if result.domain_result is not None:
        domain_result = freeze_json_object(
            result.domain_result,
            max_bytes=max_domain_result_bytes,
            max_depth=max_json_depth,
            max_collection_items=max_collection_items,
        )
    safe_payload = None
    if result.egress.safe_payload is not None:
        safe_payload = freeze_json_object(
            result.egress.safe_payload,
            max_bytes=max_model_payload_bytes,
            max_depth=max_json_depth,
            max_collection_items=max_collection_items,
        )

    disposition = result.egress.disposition
    policy_version = result.egress.policy_version
    reason_code = result.egress.reason_code
    if disposition is EgressDisposition.ALLOWED:
        if result.status is not CapabilityStatus.SUCCESS or safe_payload is None or not safe_payload:
            raise ContractViolation("core.invalid_result")
        if not isinstance(policy_version, str) or not policy_version.strip() or reason_code is not None:
            raise ContractViolation("core.invalid_result")
    elif disposition is EgressDisposition.DENIED:
        if result.status not in (CapabilityStatus.SUCCESS, CapabilityStatus.MODEL_EGRESS_DENIED):
            raise ContractViolation("core.invalid_result")
        if safe_payload is not None or not isinstance(policy_version, str) or not policy_version.strip():
            raise ContractViolation("core.invalid_result")
        if not isinstance(reason_code, str) or not _FAILURE_CODE_PATTERN.fullmatch(reason_code):
            raise ContractViolation("core.invalid_result")
    elif disposition is EgressDisposition.NOT_APPLICABLE:
        if safe_payload is not None or policy_version is not None or reason_code is not None:
            raise ContractViolation("core.invalid_result")

    failure_statuses = {
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.INVALID_ARGUMENT,
        CapabilityStatus.UNAUTHENTICATED,
        CapabilityStatus.FORBIDDEN,
        CapabilityStatus.TIMEOUT,
        CapabilityStatus.DOWNSTREAM_FAILURE,
        CapabilityStatus.INTERNAL_FAILURE,
    }
    if result.status is CapabilityStatus.SUCCESS:
        if domain_result is None or result.failure is not None:
            raise ContractViolation("core.invalid_result")
    elif result.status is CapabilityStatus.NO_RESULT:
        if disposition is not EgressDisposition.NOT_APPLICABLE or result.failure is not None:
            raise ContractViolation("core.invalid_result")
    elif result.status in failure_statuses:
        if domain_result is not None or disposition is not EgressDisposition.NOT_APPLICABLE or result.failure is None:
            raise ContractViolation("core.invalid_result")
    elif result.status is CapabilityStatus.MODEL_EGRESS_DENIED:
        if disposition is not EgressDisposition.DENIED or result.failure is None:
            raise ContractViolation("core.invalid_result")
    else:
        raise ContractViolation("core.invalid_result")
    if result.failure is not None and not isinstance(result.failure, FailureDetail):
        raise ContractViolation("core.invalid_result")

    return CapabilityResult(
        status=result.status,
        domain_result=domain_result,
        egress=ModelEgressResult(
            disposition=disposition,
            policy_version=policy_version,
            safe_payload=safe_payload,
            reason_code=reason_code,
        ),
        failure=result.failure,
    )
