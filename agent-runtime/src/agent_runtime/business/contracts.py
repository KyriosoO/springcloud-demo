from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Generic, Literal, NewType, Protocol, TypeVar

from agent_runtime.capability_api.action_resolution import LocalActionResolver
from agent_runtime.capability_api.contracts import (
    CapabilityArgumentValidator,
    CapabilityDescriptor,
    CancellationSignal,
    JsonObject,
    JsonScalar,
    OpaqueUserToken,
    freeze_json_object,
)
from agent_runtime.business.wire_json import CanonicalBusinessJsonBody

BusinessDomainId = NewType("BusinessDomainId", str)
BusinessServiceKey = NewType("BusinessServiceKey", str)


class ConstraintDimension(StrEnum):
    PAGE_SIZE = "page_size"
    RESULT_COUNT = "result_count"
    TIME_RANGE_DAYS = "time_range_days"
    FILTER_FIELDS = "filter_fields"
    SORT_FIELDS = "sort_fields"


class BusinessFieldValueType(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    TEXT = "text"
    IDENTIFIER = "identifier"


class BusinessQueryValueType(StrEnum):
    TEXT = "text"
    IDENTIFIER = "identifier"
    DECIMAL = "decimal"
    INTEGER = "integer"
    SORT_LIST = "sort_list"


class BusinessQueryOperator(StrEnum):
    EQ = "eq"
    CONTAINS = "contains"
    GT = "gt"
    LT = "lt"


class BusinessInputExposure(StrEnum):
    MODEL_LITERAL = "model_literal"
    PROTECTED_REF = "protected_ref"


class BusinessTextPolicyId(StrEnum):
    SAFE_TOKEN = "safe_token"
    SAFE_CONTAINS_TOKEN = "safe_contains_token"


class BusinessCombinationRuleKind(StrEnum):
    AT_LEAST_ONE = "at_least_one"
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"
    ALL_OR_NONE = "all_or_none"


class DataClass(StrEnum):
    PUBLIC = "public"
    BUSINESS_INTERNAL = "business_internal"
    PERSONAL_IDENTIFIER = "personal_identifier"
    EMPLOYEE_IDENTIFIER = "employee_identifier"
    TRANSACTION_IDENTIFIER = "transaction_identifier"
    FINANCIAL_ACCOUNT = "financial_account"
    FINANCIAL_VALUE = "financial_value"
    CONTACT = "contact"
    CREDENTIAL_OR_SECRET = "credential_or_secret"
    FREE_TEXT_SENSITIVE = "free_text_sensitive"
    UNKNOWN = "unknown"


class BusinessAnswerMode(StrEnum):
    STRUCTURED_ONLY = "structured_only"
    MODEL_ASSISTED = "model_assisted"


class BusinessFieldTransform(StrEnum):
    IDENTITY_SCALAR = "identity_scalar"
    BOUNDED_TEXT = "bounded_text"
    MASK_KEEP_LAST4 = "mask_keep_last4"
    DATE_ONLY = "date_only"
    DECIMAL_2 = "decimal_2"
    ENUM_CODE = "enum_code"


class BusinessServiceFailureKind(StrEnum):
    INVALID_ARGUMENT = "invalid_argument"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    UNAVAILABLE = "unavailable"


class BusinessTransportFailureKind(StrEnum):
    TIMEOUT = "timeout"
    RESPONSE_TOO_LARGE = "response_too_large"
    TLS_OR_CONNECT = "tls_or_connect"
    PROTOCOL = "protocol"


class InvalidBusinessArguments(ValueError):
    pass


class InvalidBusinessWireResponse(ValueError):
    pass


class BusinessProjectionError(ValueError):
    pass


class BusinessTransportFailure(RuntimeError):
    __slots__ = ("kind",)

    def __init__(self, kind: BusinessTransportFailureKind) -> None:
        super().__init__(kind.value)
        self.kind = kind


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessContractLimits:
    max_page_size: int | None
    max_result_count: int | None
    max_time_range_days: int | None
    max_timeout_ms: int
    max_request_bytes: int
    max_decimal_abs: str | None = None
    max_decimal_scale: int | None = None
    fixed_page: int | None = None
    allowed_sort_directions: frozenset[str] = frozenset()
    max_sort_items: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldTransformSelection:
    field_id: str
    transform_id: BusinessFieldTransform


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryFieldDefinition:
    logical_name: str
    model_safe_description: str
    value_type: BusinessQueryValueType
    allowed_operators: frozenset[BusinessQueryOperator]
    input_exposure: BusinessInputExposure
    required: bool
    allow_negative: bool = False
    max_text_chars: int | None = None
    minimum_integer: int | None = None
    maximum_integer: int | None = None
    text_policy_id: BusinessTextPolicyId | None = None
    enum_values: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessCombinationRule:
    rule_id: str
    kind: BusinessCombinationRuleKind
    field_names: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryFieldSettings:
    logical_name: str
    enabled: bool
    model_safe_description: str
    allowed_operators: tuple[BusinessQueryOperator, ...]
    required: bool
    max_text_chars: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessActionSettings:
    enabled: bool
    max_page_size: int | None
    max_result_count: int | None
    max_time_range_days: int | None
    allowed_filter_field_ids: tuple[str, ...] | None
    allowed_sort_field_ids: tuple[str, ...] | None
    user_result_field_ids: tuple[str, ...]
    model_field_ids: tuple[str, ...]
    user_transforms: tuple[FieldTransformSelection, ...]
    model_transforms: tuple[FieldTransformSelection, ...]
    timeout_ms: int
    config_version: str = "legacy-v1"
    code_contract_version: str = "legacy-v1"
    service_contract_ref: str = "legacy-v1"
    query_fields: tuple[BusinessQueryFieldSettings, ...] = ()
    combination_rule_ids: tuple[str, ...] = ()
    max_decimal_abs: str | None = None
    max_decimal_scale: int | None = None
    fixed_page: int | None = None
    allowed_sort_directions: tuple[str, ...] | None = None
    max_sort_items: int | None = None


TRecord = TypeVar("TRecord")
TValue = TypeVar("TValue")
TRecord_co = TypeVar("TRecord_co", covariant=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessFieldDefinition(Generic[TRecord, TValue]):
    field_id: str
    value_type: BusinessFieldValueType
    data_class: DataClass
    extractor: Callable[[TRecord], TValue | None]
    user_visible_by_code: bool
    model_candidate_by_code: bool
    allowed_user_transforms: frozenset[BusinessFieldTransform]
    allowed_model_transforms: frozenset[BusinessFieldTransform]
    enum_values: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessHttpStatusSemantics:
    http_204_is_no_result: bool = False
    http_400_is_invalid_argument: bool = False
    http_404_is_no_result: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessHttpRequest:
    method: Literal["GET", "POST"]
    relative_path: str
    query: tuple[tuple[str, str], ...]
    json_body: CanonicalBusinessJsonBody | None

    def __post_init__(self) -> None:
        if not self.relative_path.startswith("/") or self.relative_path.startswith("//") or ".." in self.relative_path or "\\" in self.relative_path or any(marker in self.relative_path for marker in ("#", "?", ":")):
            raise ValueError("business.invalid_relative_path")
        if self.method == "GET" and self.json_body is not None:
            raise ValueError("business.get_body_forbidden")
        if self.method == "POST" and self.json_body is None:
            raise ValueError("business.post_body_required")
        if tuple(sorted(self.query)) != self.query or len({name for name, _ in self.query}) != len(self.query):
            raise ValueError("business.invalid_query")


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundedBusinessHttpResponse:
    status_code: int
    content_type: str | None
    body: bytes | None


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessResultCoverage:
    returned_count: int
    truncated: bool
    total_count: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessRecordsResult(Generic[TRecord_co]):
    records: tuple[TRecord_co, ...]
    coverage: BusinessResultCoverage


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessNoResult:
    coverage: BusinessResultCoverage


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessFailureResult:
    kind: BusinessServiceFailureKind


BusinessServiceResult = BusinessRecordsResult[TRecord] | BusinessNoResult | BusinessFailureResult


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessUserField:
    field_id: str
    value: JsonScalar


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessUserRecord:
    record_ref: str
    fields: tuple[BusinessUserField, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessUserResult:
    capability_id: str
    records: tuple[BusinessUserRecord, ...]
    coverage: BusinessResultCoverage

    def to_domain_result(self) -> JsonObject:
        return freeze_json_object(
            {
                "schema_version": 1,
                "capability_id": self.capability_id,
                "records": tuple(
                    {"record_ref": item.record_ref, "fields": {field.field_id: field.value for field in item.fields}}
                    for item in self.records
                ),
                "coverage": {
                    "returned_count": self.coverage.returned_count,
                    "truncated": self.coverage.truncated,
                    "total_count": self.coverage.total_count,
                },
            },
            max_bytes=1048576, max_depth=8, max_collection_items=256,
        )


TInput = TypeVar("TInput")
TWireRequest = TypeVar("TWireRequest")
TWireResponse = TypeVar("TWireResponse")
TInput_contra = TypeVar("TInput_contra", contravariant=True)
TWireRequest_co = TypeVar("TWireRequest_co", covariant=True)
TWireRequest_contra = TypeVar("TWireRequest_contra", contravariant=True)
TWireResponse_co = TypeVar("TWireResponse_co", covariant=True)
TWireResponse_contra = TypeVar("TWireResponse_contra", contravariant=True)


class BusinessRequestMapper(Protocol[TInput_contra, TWireRequest_co]):
    def map(self, input: TInput_contra, settings: BusinessActionSettings) -> TWireRequest_co: ...


class BusinessWireCodec(Protocol[TWireRequest_contra, TWireResponse_co]):
    def encode(self, request: TWireRequest_contra) -> BusinessHttpRequest: ...
    def decode_success(self, *, request: TWireRequest_contra, response: BoundedBusinessHttpResponse) -> TWireResponse_co: ...


class BusinessResponseNormalizer(Protocol[TWireResponse_contra, TRecord_co]):
    def normalize_success(self, response: TWireResponse_contra) -> BusinessServiceResult[TRecord_co]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessActionDefinition(Generic[TInput, TWireRequest, TWireResponse, TRecord]):
    descriptor: CapabilityDescriptor
    domain_id: BusinessDomainId
    service_key: BusinessServiceKey
    argument_validator: CapabilityArgumentValidator[TInput]
    request_mapper: BusinessRequestMapper[TInput, TWireRequest]
    wire_codec: BusinessWireCodec[TWireRequest, TWireResponse]
    response_normalizer: BusinessResponseNormalizer[TWireResponse, TRecord]
    http_status_semantics: BusinessHttpStatusSemantics
    applicable_dimensions: frozenset[ConstraintDimension]
    filter_field_ids_by_code: frozenset[str]
    sort_field_ids_by_code: frozenset[str]
    field_definitions: tuple[BusinessFieldDefinition[TRecord, Any], ...]
    required_user_field_ids: tuple[str, ...]
    answer_mode: BusinessAnswerMode
    contract_limits: BusinessContractLimits
    query_fields: tuple[BusinessQueryFieldDefinition, ...] = ()
    combination_rules: tuple[BusinessCombinationRule, ...] = ()
    code_contract_version: str = "legacy-v1"
    service_contract_ref: str = "legacy-v1"
    local_action_resolver: LocalActionResolver | None = None


class BusinessHttpClient(Protocol):
    async def execute(
        self,
        *,
        request: BusinessHttpRequest,
        user_token: OpaqueUserToken,
        call_deadline: float,
        cancellation: CancellationSignal,
    ) -> BoundedBusinessHttpResponse: ...
