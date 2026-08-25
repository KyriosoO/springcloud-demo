from __future__ import annotations

from collections.abc import Mapping

from agent_runtime.capability_api.contracts import JsonObject, JsonValue, freeze_json_object
from agent_runtime.model.contracts import (
    BusinessQueryPlanTaskInput,
    InvalidModelOutput,
    ModelCallContext,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTaskDefinition,
    ModelTaskId,
    ModelTransportError,
    StructuredFinishKind,
    StructuredModelGateway,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
    canonical_object_json,
)
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object


BUSINESS_QUERY_PLAN_TASK_VERSION = "business-query-plan-v4"
BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION = (
    "Create exactly one logical Business QueryPlan from the supplied question and catalog. "
    "Return exactly one JSON object with exactly domain, action, and arguments; output no other text. "
    "Choose one enabled domain and action only, and include all and only necessary logical arguments. "
    "For employee.search or transaction.search, arguments must contain exactly filters, page, size, "
    "and sorts; employee.search may also include the catalog-approved keyword. Each filter must contain "
    "exactly field, operator, and value. Each filter value and keyword must use exactly one tagged value: "
    "literal or value_ref. For employee.semantic_search, arguments must contain exactly query and size, "
    "where query is a tagged literal; never add filters to semantic search. "
    "A protected field may only reference an existing opaque slot such as slot-1 and must never reproduce "
    "or guess its value. Follow every field type, per-field operator, combination, decimal, date, page, "
    "size, sort limit, and configured input exposure. An amount is a canonical decimal string, dates "
    "must carry an explicit numeric UTC offset, and an open interval uses two filters on the same field. "
    "Never output SQL, ES DSL, URLs, endpoints, indexes, tables, columns, headers, JWTs, roles, class names, "
    "method names, implementation details, a second action, fallback, or another domain suggestion. "
    "Preserve the complete user intent: every requested field, condition, and operator must be explicitly "
    "enabled in the supplied catalog. If any requested date, time, location, field, condition, or operator "
    "cannot be expressed, never omit that condition, broaden the query, substitute another condition, or "
    "return an executable action with empty or partial arguments. For '帮我查一下在上海的员工', when "
    "contact_address and contains are enabled, return exactly "
    '{"domain":"employee","action":"employee.search","arguments":{"filters":'
    '[{"field":"contact_address","operator":"contains","value":{"literal":"上海"}}],'
    '"page":1,"size":20,"sorts":[]}}. '
    "For '查询具备金融风控经验的员工', when semantic search is enabled, return exactly "
    '{"domain":"employee","action":"employee.semantic_search","arguments":'
    '{"query":{"literal":"金融风控经验"},"size":20}}. '
    "For '按语义搜索金融风控经验并限定上海员工', always return exactly "
    '{"domain":"employee","action":"unsupported","arguments":{}}. '
    "Neither employee.semantic_search nor employee.search can represent both the requested semantic "
    "meaning and the required Shanghai location in one enabled action. Never drop the location, "
    "drop the semantic requirement, select either action, or broaden the requested result. "
    "For a relative transaction date question such as '查询今天发生的交易', when the catalog does "
    "not provide an approved current-date or clock context, always return exactly "
    '{"domain":"transaction","action":"unsupported","arguments":{}}. '
    "This unsupported rule still applies when trans_date is enabled; never infer today's date, "
    "invent a time window, omit the requested date, or issue an executable transaction plan. "
    "For an employee location question such as '帮我查看上海的员工', when no location field is enabled, "
    'return exactly {"domain":"employee","action":"unsupported","arguments":{}}. '
    "When a business domain is clear but no enabled action can represent the complete question, keep that "
    "catalog domain and return action unsupported with empty arguments. When no catalog domain applies, return exactly "
    '{"domain":"unsupported","action":"unsupported","arguments":{}}.'
)


def build_business_query_plan_task_definition(
    *,
    timeout_ms: int,
    max_output_bytes: int = 16384,
    max_json_depth: int = 8,
    max_collection_items: int = 128,
    max_input_bytes: int = 65536,
    max_output_tokens: int = 2048,
) -> ModelTaskDefinition[BusinessQueryPlanTaskInput, JsonObject]:
    for value in (
        max_output_bytes,
        max_json_depth,
        max_collection_items,
        max_input_bytes,
        max_output_tokens,
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("model.invalid_business_query_plan_limit")

    def build_request(input: BusinessQueryPlanTaskInput) -> StructuredModelRequest:
        try:
            payload = freeze_json_object(
                {
                    "catalog": input.catalog,
                    "catalog_snapshot_id": input.catalog_snapshot_id,
                    "question": input.minimized_question,
                },
                max_bytes=max_input_bytes,
                max_depth=8,
                max_collection_items=512,
            )
        except ValueError as exc:
            raise ModelInputDenied("model.business_query_plan_input_too_large") from exc
        return StructuredModelRequest(
            task_id=definition.task_id,
            task_version=definition.task_version,
            system_instruction=BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
            user_payload_json=canonical_object_json(payload),
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=max_output_tokens,
        )

    def parse_response(response: StructuredModelResponse) -> JsonObject:
        return decode_business_query_plan_output(
            response,
            max_output_bytes=max_output_bytes,
            max_json_depth=max_json_depth,
            max_collection_items=max_collection_items,
        )

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version=BUSINESS_QUERY_PLAN_TASK_VERSION,
        input_type=BusinessQueryPlanTaskInput,
        max_input_bytes=max_input_bytes,
        timeout_ms=timeout_ms,
        max_output_tokens=max_output_tokens,
        build_request=build_request,
        parse_response=parse_response,
    )
    return definition


class DeepSeekBusinessQueryPlanGenerator:
    __slots__ = ("_definition", "_gateway")

    def __init__(
        self,
        *,
        gateway: StructuredModelGateway,
        definition: ModelTaskDefinition[BusinessQueryPlanTaskInput, JsonObject],
    ) -> None:
        self._gateway = gateway
        self._definition = definition

    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject:
        result = await self._gateway.generate(
            definition=self._definition,
            input=input,
            context=context,
        )
        if result.failure_kind is not None:
            raise ModelTransportError(result.failure_kind)
        if result.output is None:
            raise ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
        return result.output


def decode_business_query_plan_output(
    response: StructuredModelResponse,
    *,
    max_output_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> JsonObject:
    if (
        response.finish_kind is not StructuredFinishKind.STOP
        or response.tool_calls
        or not isinstance(response.content, str)
        or not response.content
    ):
        raise InvalidModelOutput("model.business_query_plan_response_invalid")
    value = parse_unique_json_object(
        response.content,
        max_bytes=max_output_bytes,
        max_depth=max_json_depth,
        max_items=max_collection_items,
    )
    if _contains_forbidden_json_value(value):
        raise InvalidModelOutput("model.business_query_plan_response_invalid")
    return value


def _contains_forbidden_json_value(value: JsonValue) -> bool:
    if value is None or isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(_contains_forbidden_json_value(item) for item in value.values())
    if isinstance(value, tuple):
        return any(_contains_forbidden_json_value(item) for item in value)
    return False
