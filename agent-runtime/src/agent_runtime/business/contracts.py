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
    DATETIME = "datetime"
    INTEGER = "integer"
    SORT_LIST = "sort_list"


class BusinessQueryOperator(StrEnum):
    EQ = "eq"
    CONTAINS = "contains"
    PREFIX = "prefix"
    IN = "in"
    GT = "gt"
    LT = "lt"


class BusinessInputExposure(StrEnum):
    MODEL_LITERAL = "model_literal"
    LITERAL = "literal"
    PROTECTED_REF = "protected_ref"
    LITERAL_OR_PROTECTED_REF = "literal_or_protected_ref"


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
    MASK_NAME = "mask_name"
    MASK_ADDRESS = "mask_address"
    MASK_CONTACT = "mask_contact"
    DATE_ONLY = "date_only"
    DATETIME_ISO = "datetime_iso"
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
    max_page: int | None = None


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
    service_field: str | None = None


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
    service_field: str | None = None
    input_exposure: BusinessInputExposure | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryActionContract:
    action_id: str
    domain_id: BusinessDomainId
    service_key: BusinessServiceKey
    code_contract_version: str
    service_contract_ref: str
    query_fields: tuple[BusinessQueryFieldDefinition, ...]
    allowed_sort_fields: frozenset[str]
    max_page: int
    max_page_size: int
    max_result_count: int
    max_timeout_ms: int
    keyword_service_field_ids: tuple[str, ...] = ()
    semantic_profile_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessResultFieldContract:
    field_id: str
    value_type: BusinessFieldValueType
    data_class: DataClass
    user_transform: BusinessFieldTransform
    model_transform: BusinessFieldTransform | None
    required: bool = False


def business_query_v2_result_contracts(
    action_id: str,
) -> tuple[BusinessResultFieldContract, ...]:
    if action_id in {"employee.search", "employee.semantic_search"}:
        return (
            BusinessResultFieldContract(
                field_id="contact_address", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.CONTACT, user_transform=BusinessFieldTransform.MASK_ADDRESS,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="chinese_name", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.PERSONAL_IDENTIFIER,
                user_transform=BusinessFieldTransform.MASK_NAME,
                model_transform=None, required=True,
            ),
            BusinessResultFieldContract(
                field_id="employee_identifier", value_type=BusinessFieldValueType.IDENTIFIER,
                data_class=DataClass.PERSONAL_IDENTIFIER,
                user_transform=BusinessFieldTransform.MASK_KEEP_LAST4,
                model_transform=None, required=True,
            ),
            BusinessResultFieldContract(
                field_id="member_no", value_type=BusinessFieldValueType.IDENTIFIER,
                data_class=DataClass.EMPLOYEE_IDENTIFIER,
                user_transform=BusinessFieldTransform.MASK_KEEP_LAST4,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="phone_no", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.CONTACT,
                user_transform=BusinessFieldTransform.MASK_CONTACT,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="email", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.CONTACT,
                user_transform=BusinessFieldTransform.MASK_CONTACT,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="position", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.BUSINESS_INTERNAL,
                user_transform=BusinessFieldTransform.BOUNDED_TEXT,
                model_transform=BusinessFieldTransform.BOUNDED_TEXT,
            ),
        )
    if action_id == "transaction.search":
        return (
            BusinessResultFieldContract(
                field_id="trans_id", value_type=BusinessFieldValueType.IDENTIFIER,
                data_class=DataClass.TRANSACTION_IDENTIFIER,
                user_transform=BusinessFieldTransform.MASK_KEEP_LAST4,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="trans_type", value_type=BusinessFieldValueType.TEXT,
                data_class=DataClass.BUSINESS_INTERNAL,
                user_transform=BusinessFieldTransform.BOUNDED_TEXT,
                model_transform=BusinessFieldTransform.BOUNDED_TEXT, required=True,
            ),
            BusinessResultFieldContract(
                field_id="trans_date", value_type=BusinessFieldValueType.DATETIME,
                data_class=DataClass.BUSINESS_INTERNAL,
                user_transform=BusinessFieldTransform.DATETIME_ISO,
                model_transform=None,
            ),
            BusinessResultFieldContract(
                field_id="amount", value_type=BusinessFieldValueType.DECIMAL,
                data_class=DataClass.FINANCIAL_VALUE,
                user_transform=BusinessFieldTransform.DECIMAL_2,
                model_transform=BusinessFieldTransform.DECIMAL_2, required=True,
            ),
        )
    raise ValueError("business.unknown_action_contract")


def business_query_v2_action_contracts() -> tuple[BusinessQueryActionContract, ...]:
    text_ops = frozenset(
        {
            BusinessQueryOperator.EQ,
            BusinessQueryOperator.CONTAINS,
            BusinessQueryOperator.PREFIX,
            BusinessQueryOperator.IN,
        }
    )
    exact = frozenset({BusinessQueryOperator.EQ})
    employee_fields = (
        BusinessQueryFieldDefinition(
            logical_name="contact_address", service_field="contactAddress",
            model_safe_description="员工联系地点的非敏感城市片段",
            value_type=BusinessQueryValueType.TEXT, allowed_operators=text_ops,
            input_exposure=BusinessInputExposure.LITERAL_OR_PROTECTED_REF,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
        ),
        BusinessQueryFieldDefinition(
            logical_name="chinese_name", service_field="chineseName",
            model_safe_description="当前请求中员工姓名的受保护引用",
            value_type=BusinessQueryValueType.TEXT, allowed_operators=text_ops,
            input_exposure=BusinessInputExposure.PROTECTED_REF,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
        ),
        BusinessQueryFieldDefinition(
            logical_name="employee_identifier", service_field="idCardNo",
            model_safe_description="当前请求中员工标识的受保护引用",
            value_type=BusinessQueryValueType.IDENTIFIER, allowed_operators=exact,
            input_exposure=BusinessInputExposure.PROTECTED_REF, required=False,
        ),
        BusinessQueryFieldDefinition(
            logical_name="member_no", service_field="memberNo",
            model_safe_description="当前请求中会员编号的受保护引用",
            value_type=BusinessQueryValueType.IDENTIFIER,
            allowed_operators=frozenset({BusinessQueryOperator.EQ, BusinessQueryOperator.PREFIX}),
            input_exposure=BusinessInputExposure.PROTECTED_REF, required=False,
        ),
        BusinessQueryFieldDefinition(
            logical_name="phone_no", service_field="phoneNo",
            model_safe_description="当前请求中员工联系电话的受保护引用",
            value_type=BusinessQueryValueType.TEXT,
            allowed_operators=frozenset({BusinessQueryOperator.EQ, BusinessQueryOperator.PREFIX}),
            input_exposure=BusinessInputExposure.PROTECTED_REF,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_TOKEN,
        ),
        BusinessQueryFieldDefinition(
            logical_name="email", service_field="email",
            model_safe_description="当前请求中员工邮箱的受保护引用",
            value_type=BusinessQueryValueType.TEXT, allowed_operators=exact,
            input_exposure=BusinessInputExposure.PROTECTED_REF,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_TOKEN,
        ),
        BusinessQueryFieldDefinition(
            logical_name="position", service_field="position",
            model_safe_description="员工职位的非敏感业务文本",
            value_type=BusinessQueryValueType.TEXT, allowed_operators=text_ops,
            input_exposure=BusinessInputExposure.LITERAL,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
        ),
    )
    employee_semantic_fields = (
        BusinessQueryFieldDefinition(
            logical_name="query", service_field="queryText",
            model_safe_description="不包含姓名、地址、标识或联系方式的员工专业能力描述",
            value_type=BusinessQueryValueType.TEXT, allowed_operators=exact,
            input_exposure=BusinessInputExposure.LITERAL,
            required=True, max_text_chars=256,
            text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
        ),
    )
    transaction_fields = (
        BusinessQueryFieldDefinition(
            logical_name="trans_id", service_field="transId",
            model_safe_description="当前请求中交易标识的受保护引用",
            value_type=BusinessQueryValueType.IDENTIFIER, allowed_operators=exact,
            input_exposure=BusinessInputExposure.PROTECTED_REF, required=False,
        ),
        BusinessQueryFieldDefinition(
            logical_name="trans_type", service_field="transType",
            model_safe_description="交易类型的精确或包含匹配业务文本",
            value_type=BusinessQueryValueType.TEXT,
            allowed_operators=frozenset({BusinessQueryOperator.EQ, BusinessQueryOperator.CONTAINS}),
            input_exposure=BusinessInputExposure.LITERAL,
            required=False, max_text_chars=128,
            text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
        ),
        BusinessQueryFieldDefinition(
            logical_name="trans_date", service_field="transDate",
            model_safe_description="包含明确时区偏移的绝对交易时间",
            value_type=BusinessQueryValueType.DATETIME,
            allowed_operators=frozenset(
                {BusinessQueryOperator.EQ, BusinessQueryOperator.GT, BusinessQueryOperator.LT}
            ),
            input_exposure=BusinessInputExposure.LITERAL, required=False,
        ),
        BusinessQueryFieldDefinition(
            logical_name="amount", service_field="amount",
            model_safe_description="最多两位小数的规范十进制交易金额",
            value_type=BusinessQueryValueType.DECIMAL,
            allowed_operators=frozenset(
                {BusinessQueryOperator.EQ, BusinessQueryOperator.GT, BusinessQueryOperator.LT}
            ),
            input_exposure=BusinessInputExposure.LITERAL,
            required=False, allow_negative=True,
        ),
    )
    return (
        BusinessQueryActionContract(
            action_id="employee.search", domain_id=BusinessDomainId("employee"),
            service_key=BusinessServiceKey("employee-service"),
            code_contract_version="employee-search-plan-v2",
            service_contract_ref="employee.es.search.v1", query_fields=employee_fields,
            allowed_sort_fields=frozenset({"chinese_name", "position"}),
            max_page=1000, max_page_size=50, max_result_count=50, max_timeout_ms=3000,
            keyword_service_field_ids=("contactAddress", "chineseName", "idCardNo"),
        ),
        BusinessQueryActionContract(
            action_id="employee.semantic_search", domain_id=BusinessDomainId("employee"),
            service_key=BusinessServiceKey("employee-service"),
            code_contract_version="employee-semantic-search-plan-v2",
            service_contract_ref="employee.es.vector-search.v1",
            query_fields=employee_semantic_fields, allowed_sort_fields=frozenset(),
            max_page=1, max_page_size=50, max_result_count=50, max_timeout_ms=10000,
            semantic_profile_id="employee-default-v1",
        ),
        BusinessQueryActionContract(
            action_id="transaction.search", domain_id=BusinessDomainId("transaction"),
            service_key=BusinessServiceKey("mq-procedure-service"),
            code_contract_version="transaction-search-plan-v2",
            service_contract_ref="transaction.search.v1", query_fields=transaction_fields,
            allowed_sort_fields=frozenset({"trans_id", "trans_type", "trans_date", "amount"}),
            max_page=1000, max_page_size=50, max_result_count=50, max_timeout_ms=5000,
        ),
    )


def business_query_v2_action_contract(action_id: str) -> BusinessQueryActionContract:
    matches = tuple(
        item for item in business_query_v2_action_contracts() if item.action_id == action_id
    )
    if len(matches) != 1:
        raise ValueError("business.unknown_action_contract")
    return matches[0]


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
    max_page: int | None = None
    keyword_enabled: bool = False
    keyword_service_field_ids: tuple[str, ...] = ()
    keyword_input_exposure: BusinessInputExposure | None = None
    keyword_max_text_chars: int | None = None
    semantic_profile_id: str | None = None


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
