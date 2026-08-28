from __future__ import annotations

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object
from agent_runtime.model.contracts import (
    BusinessQueryPlanTaskInput,
    ModelInputDenied,
    ModelTaskDefinition,
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
    canonical_object_json,
)
from agent_runtime.model.deepseek.business_query_plan import (
    DeepSeekBusinessQueryPlanGenerator,
    decode_business_query_plan_output,
)
from agent_runtime.model.deepseek.business_query_plan_v5 import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION as V5_SYSTEM_INSTRUCTION,
)


BUSINESS_QUERY_PLAN_TASK_VERSION = "business-query-plan-v6"
BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION = (
    V5_SYSTEM_INSTRUCTION
    + " Protected-reference serialization is exact: protected-ref(slot-N) is only a wrapper in the "
    "question. Inside a tagged JSON value, copy only the bare slot ID. Emit "
    "{\"value_ref\":\"slot-1\"} for one protected value and "
    "{\"value_refs\":[\"slot-1\",\"slot-2\"]} for multiple protected values. Never emit "
    "protected-ref(slot-N) as a JSON value. For one requested filter, include every semantically "
    "corresponding slot exactly once, in question order; never omit, duplicate, rename, invent, or "
    "reuse a slot in another filter unless the question explicitly applies that protected value to "
    "that separate condition."
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
                max_depth=12,
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


__all__ = (
    "BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION",
    "BUSINESS_QUERY_PLAN_TASK_VERSION",
    "DeepSeekBusinessQueryPlanGenerator",
    "build_business_query_plan_task_definition",
)
