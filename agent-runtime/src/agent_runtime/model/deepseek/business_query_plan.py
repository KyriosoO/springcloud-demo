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


BUSINESS_QUERY_PLAN_TASK_VERSION = "business-query-plan-v1"
BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION = (
    "Create exactly one logical Business QueryPlan from the supplied question and catalog. "
    "Return exactly one JSON object with exactly domain, action, and arguments; output no other text. "
    "Choose one enabled domain and action only, and include all and only necessary logical arguments. "
    "Each argument must use exactly one tagged value: literal or value_ref, as required by the catalog. "
    "A protected field may only reference an existing opaque slot such as slot-1 and must never reproduce "
    "or guess its value. Follow every field type, operator, combination, decimal, size, and sort limit. "
    "Never output SQL, ES DSL, URLs, endpoints, indexes, tables, columns, headers, JWTs, roles, class names, "
    "method names, implementation details, a second action, fallback, or another domain suggestion. "
    "When a business domain is clear but no enabled action can represent the question, keep that catalog "
    "domain and return action unsupported with empty arguments. When no catalog domain applies, return exactly "
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
