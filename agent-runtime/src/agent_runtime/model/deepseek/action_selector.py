from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import ModelNodeFailure, ModelNodeFailureKind
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelInputDenied,
    ModelTaskDefinition,
    ModelTaskId,
    QuestionEgressDisposition,
    StructuredFinishKind,
    StructuredModelGateway,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
    canonical_object_json,
)
from agent_runtime.model.deepseek.errors import to_model_node_failure
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object
from agent_runtime.model.deepseek.tools import (
    UNSUPPORTED_CAPABILITY_ID,
    InvalidCapabilityCatalog,
    capability_ids_from_catalog,
    project_capability_catalog,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


ACTION_SELECTION_SYSTEM_INSTRUCTION = (
    "Select exactly one capability ID from the supplied catalog. Return exactly one JSON object and no "
    "other text. Example JSON: {\"capability_id\":\"knowledge.query\"}. The only allowed field is "
    "capability_id. Use agent_unsupported when no catalog entry applies. Never generate query conditions, "
    "identifiers, amounts, pagination, sorting, tool calls, invented IDs, or additional fields."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionSelectionTaskInput:
    minimized_question: str
    catalog: JsonObject


def build_action_selection_task_definition(
    *,
    timeout_ms: int,
    max_input_bytes: int = 65536,
    max_output_tokens: int = 512,
) -> ModelTaskDefinition[ActionSelectionTaskInput, str]:
    def build_request(input: ActionSelectionTaskInput) -> StructuredModelRequest:
        capabilities = input.catalog.get("capabilities")
        try:
            payload = freeze_json_object(
                {
                    "capabilities": capabilities,
                    "question": input.minimized_question,
                },
                max_bytes=max_input_bytes,
                max_depth=8,
                max_collection_items=512,
            )
        except ValueError as exc:
            raise ModelInputDenied("model.action_input_too_large") from exc
        return StructuredModelRequest(
            task_id=definition.task_id,
            task_version=definition.task_version,
            system_instruction=ACTION_SELECTION_SYSTEM_INSTRUCTION,
            user_payload_json=canonical_object_json(payload),
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=max_output_tokens,
        )

    def parse_response(response: StructuredModelResponse) -> str:
        if (
            response.finish_kind is not StructuredFinishKind.STOP
            or response.tool_calls
            or not isinstance(response.content, str)
            or not response.content
        ):
            raise InvalidModelOutput("model.action_response_invalid")
        return response.content

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.ACTION_SELECTION,
        task_version="action-selection-v4",
        input_type=ActionSelectionTaskInput,
        max_input_bytes=max_input_bytes,
        timeout_ms=timeout_ms,
        max_output_tokens=max_output_tokens,
        build_request=build_request,
        parse_response=parse_response,
    )
    return definition


class DeepSeekCapabilitySelector:
    __slots__ = ("_context", "_definition", "_gateway", "_guard", "_max_output_bytes")

    def __init__(
        self,
        *,
        guard: QuestionEgressGuard,
        gateway: StructuredModelGateway,
        context: ModelCallContextAccessor,
        definition: ModelTaskDefinition[ActionSelectionTaskInput, str],
        max_argument_bytes: int = 16384,
    ) -> None:
        if (
            not isinstance(max_argument_bytes, int)
            or isinstance(max_argument_bytes, bool)
            or max_argument_bytes <= 0
        ):
            raise ValueError("model.invalid_action_output_limit")
        self._guard = guard
        self._gateway = gateway
        self._context = context
        self._definition = definition
        self._max_output_bytes = max_argument_bytes

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        decision = self._guard.evaluate(input.question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return _failure(ModelNodeFailureKind.INPUT_DENIED)
        assert decision.minimized_question is not None
        try:
            catalog = project_capability_catalog(input.descriptors)
            allowed_capability_ids = capability_ids_from_catalog(catalog)
            context = self._context.require_current()
        except InvalidCapabilityCatalog:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        except ValueError:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        result = await self._gateway.generate(
            definition=self._definition,
            input=ActionSelectionTaskInput(
                minimized_question=decision.minimized_question,
                catalog=catalog,
            ),
            context=context,
        )
        if result.failure_kind is not None:
            return CapabilitySelectionDecision(
                kind=CapabilitySelectionDecisionKind.FAILURE,
                failure=to_model_node_failure(result.failure_kind),
            )
        if result.output is None:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        try:
            capability_id = decode_action_selection_output(
                result.output,
                catalog=catalog,
                max_bytes=self._max_output_bytes,
            )
        except InvalidModelOutput:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        if capability_id not in allowed_capability_ids:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        if capability_id == UNSUPPORTED_CAPABILITY_ID:
            return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)
        return CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id=capability_id,
        )


def decode_action_selection_output(
    content: str,
    *,
    catalog: JsonObject,
    max_bytes: int,
) -> str:
    value = parse_unique_json_object(
        content,
        max_bytes=max_bytes,
        max_depth=2,
        max_items=2,
    )
    if set(value) != {"capability_id"}:
        raise InvalidModelOutput("model.action_response_invalid")
    capability_id = value.get("capability_id")
    if (
        not isinstance(capability_id, str)
        or capability_id not in capability_ids_from_catalog(catalog)
    ):
        raise InvalidModelOutput("model.action_response_invalid")
    return capability_id


def _failure(kind: ModelNodeFailureKind) -> CapabilitySelectionDecision:
    return CapabilitySelectionDecision(
        kind=CapabilitySelectionDecisionKind.FAILURE,
        failure=ModelNodeFailure(kind=kind),
    )


DeepSeekActionSelector = DeepSeekCapabilitySelector
