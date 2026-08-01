from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.capability_api.contracts import ActionCandidate, freeze_json_object
from agent_runtime.graph.state import (
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ModelNodeFailureKind,
)
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
    StructuredToolCall,
    StructuredToolMode,
    canonical_object_json,
)
from agent_runtime.model.deepseek.errors import to_model_node_failure
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object
from agent_runtime.model.deepseek.tools import (
    UNSUPPORTED_TOOL_NAME,
    CapabilityToolProjection,
    project_capability_tools,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


_ACTION_SYSTEM_INSTRUCTION = (
    "Select exactly one registered function tool for the user request. "
    "Do not execute tools, invent functions, or return prose. Use agent_unsupported when none applies."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionSelectionTaskInput:
    minimized_question: str
    projection: CapabilityToolProjection


def build_action_selection_task_definition(
    *,
    timeout_ms: int,
    max_input_bytes: int = 65536,
    max_output_tokens: int = 512,
) -> ModelTaskDefinition[ActionSelectionTaskInput, StructuredToolCall]:
    def build_request(input: ActionSelectionTaskInput) -> StructuredModelRequest:
        try:
            payload = freeze_json_object(
                {"question": input.minimized_question},
                max_bytes=max_input_bytes,
                max_depth=8,
                max_collection_items=256,
            )
        except ValueError as exc:
            raise ModelInputDenied("model.action_input_too_large") from exc
        return StructuredModelRequest(
            task_id=definition.task_id,
            task_version=definition.task_version,
            system_instruction=_ACTION_SYSTEM_INSTRUCTION,
            user_payload_json=canonical_object_json(payload),
            tools=input.projection.tools,
            tool_mode=StructuredToolMode.REQUIRED,
            output_mode=StructuredOutputMode.TOOL_CALLS,
            max_output_tokens=max_output_tokens,
        )

    def parse_response(response: StructuredModelResponse) -> StructuredToolCall:
        if (
            response.finish_kind is not StructuredFinishKind.TOOL_CALLS
            or len(response.tool_calls) != 1
            or (response.content is not None and bool(response.content.strip()))
        ):
            raise InvalidModelOutput("model.action_response_invalid")
        return response.tool_calls[0]

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.ACTION_SELECTION,
        task_version="action-selection-v1",
        input_type=ActionSelectionTaskInput,
        max_input_bytes=max_input_bytes,
        timeout_ms=timeout_ms,
        max_output_tokens=max_output_tokens,
        build_request=build_request,
        parse_response=parse_response,
    )
    return definition


class DeepSeekActionSelector:
    __slots__ = ("_context", "_definition", "_gateway", "_guard", "_max_argument_bytes")

    def __init__(
        self,
        *,
        guard: QuestionEgressGuard,
        gateway: StructuredModelGateway,
        context: ModelCallContextAccessor,
        definition: ModelTaskDefinition[ActionSelectionTaskInput, StructuredToolCall],
        max_argument_bytes: int = 16384,
    ) -> None:
        self._guard = guard
        self._gateway = gateway
        self._context = context
        self._definition = definition
        self._max_argument_bytes = max_argument_bytes

    async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision:
        decision = self._guard.evaluate(input.question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return _failure(ModelNodeFailureKind.INPUT_DENIED)
        assert decision.minimized_question is not None
        try:
            projection = project_capability_tools(input.descriptors)
            context = self._context.require_current()
        except ValueError:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        result = await self._gateway.generate(
            definition=self._definition,
            input=ActionSelectionTaskInput(
                minimized_question=decision.minimized_question,
                projection=projection,
            ),
            context=context,
        )
        if result.failure_kind is not None:
            return ActionSelectionDecision(
                kind=ActionSelectionDecisionKind.FAILURE,
                failure=to_model_node_failure(result.failure_kind),
            )
        call = result.output
        if call is None:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        if call.name == UNSUPPORTED_TOOL_NAME:
            try:
                arguments = parse_unique_json_object(
                    call.arguments_json,
                    max_bytes=self._max_argument_bytes,
                    max_depth=8,
                    max_items=256,
                )
            except InvalidModelOutput:
                return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
            if arguments:
                return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
            return ActionSelectionDecision(kind=ActionSelectionDecisionKind.UNSUPPORTED)
        capability_id = projection.capability_by_tool.get(call.name)
        if capability_id is None:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        try:
            arguments = parse_unique_json_object(
                call.arguments_json,
                max_bytes=self._max_argument_bytes,
                max_depth=8,
                max_items=256,
            )
            candidate = ActionCandidate(capability_id=capability_id, arguments=arguments)
        except ValueError:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        return ActionSelectionDecision(
            kind=ActionSelectionDecisionKind.CANDIDATE,
            candidate=candidate,
        )


def _failure(kind: ModelNodeFailureKind) -> ActionSelectionDecision:
    from agent_runtime.graph.state import ModelNodeFailure

    return ActionSelectionDecision(
        kind=ActionSelectionDecisionKind.FAILURE,
        failure=ModelNodeFailure(kind=kind),
    )
