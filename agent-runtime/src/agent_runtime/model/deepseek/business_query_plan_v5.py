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


BUSINESS_QUERY_PLAN_TASK_VERSION = "business-query-plan-v5"
BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION = (
    "Create exactly one logical Business QueryPlan from the complete supplied question and catalog. "
    "Return exactly one JSON object with exactly domain, action, and arguments; output no other text. "
    "Natural-language phrasing, domain, action, fields, operators, AND/OR intent, and single/multiple "
    "values are your responsibility. Do not rely on fixed command words. Use one enabled action only. "
    "For employee.search and transaction.search, arguments contain exactly filters, page, size, sorts; "
    "employee.search may include only its catalog-approved keyword. Every filter contains exactly field, "
    "operator, value. A value is exactly one tagged object: literal, value_ref, or value_refs. Follow the "
    "catalog operator contract: scalar operators use one literal or value_ref; multi-value operators use "
    "a literal array or value_refs. Never use exact in for prefix-any or contains-any intent. Preserve AND "
    "by emitting separate filters; preserve OR only through an enabled multi-value operator. Use only the "
    "catalog-approved same-field combinations and never merge, omit, or weaken a requested condition. "
    "A protected field must use only supplied opaque slots. Never reveal, reproduce, infer, or guess the "
    "protected values. For employee.semantic_search, arguments contain exactly query and size, query is a "
    "tagged literal, and filters are forbidden. Follow all field types, exposures, cardinalities, value "
    "limits, combinations, pages, sizes, and sorts in the catalog. Location literals must use a catalog "
    "administrative-region alias; detailed addresses require protected references. "
    "Never output SQL, ES DSL, URLs, endpoints, indexes, tables, columns, headers, JWTs, roles, Java "
    "operator aliases, class names, method names, a second action, fallback, or another domain suggestion. "
    "When every requested condition cannot be expressed by one enabled action, keep the clear catalog "
    "domain and return action unsupported with empty arguments. When no catalog domain reliably applies, "
    "return domain unsupported, action unsupported, and empty arguments. "
    "Examples express semantics, not mandatory wording: a single protected surname uses chinese_name "
    "prefix plus one value_ref; multiple protected surnames use prefix_any plus value_refs; multiple full "
    "protected names use in plus value_refs; a surname AND name-fragment request uses separate prefix and "
    "contains filters on chinese_name; multiple public regions use contact_address contains_any with a "
    "literal array. A request phrased as a question or command must produce the same logical plan."
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
