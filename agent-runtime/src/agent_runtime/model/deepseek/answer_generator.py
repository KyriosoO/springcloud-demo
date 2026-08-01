from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    CandidateAnswer,
    GroundingDecision,
    GroundingInput,
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
from agent_runtime.model.grounding import GroundingPolicyRegistry
from agent_runtime.model.input_guard import QuestionEgressGuard


_ANSWER_SYSTEM_INSTRUCTION = (
    "Return one JSON object with exactly answer, used_fact_ids, and unsupported_claims. "
    "Use only supplied facts, cite every used fact ID, and keep unsupported_claims as an empty array. "
    'Example: {"answer":"...","used_fact_ids":["fact-0001"],"unsupported_claims":[]}'
)
_FORBIDDEN_ANSWER_TEXT = re.compile(
    r"(?i)(?:https?://|authorization|system prompt|developer message|角色权限|忽略(?:规则|指令))"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerGenerationTaskInput:
    minimized_question: str
    safe_payload: JsonObject


def build_answer_generation_task_definition(
    *,
    timeout_ms: int,
    max_input_bytes: int = 65536,
    max_output_tokens: int = 1024,
) -> ModelTaskDefinition[AnswerGenerationTaskInput, CandidateAnswer]:
    def build_request(input: AnswerGenerationTaskInput) -> StructuredModelRequest:
        try:
            payload = freeze_json_object(
                {"question": input.minimized_question, "safe_payload": input.safe_payload},
                max_bytes=max_input_bytes,
                max_depth=10,
                max_collection_items=512,
            )
        except ValueError as exc:
            raise ModelInputDenied("model.answer_input_too_large") from exc
        return StructuredModelRequest(
            task_id=definition.task_id,
            task_version=definition.task_version,
            system_instruction=_ANSWER_SYSTEM_INSTRUCTION,
            user_payload_json=canonical_object_json(payload),
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=max_output_tokens,
        )

    def parse_response(response: StructuredModelResponse) -> CandidateAnswer:
        if (
            response.finish_kind is not StructuredFinishKind.STOP
            or response.tool_calls
            or response.content is None
            or not response.content.strip()
        ):
            raise InvalidModelOutput("model.answer_response_invalid")
        parsed = parse_unique_json_object(response.content, max_bytes=16384, max_depth=6, max_items=512)
        if set(parsed) != {"answer", "used_fact_ids", "unsupported_claims"}:
            raise InvalidModelOutput("model.answer_schema_invalid")
        answer = parsed.get("answer")
        used_fact_ids = parsed.get("used_fact_ids")
        unsupported_claims = parsed.get("unsupported_claims")
        if (
            not isinstance(answer, str)
            or not isinstance(used_fact_ids, tuple)
            or not all(isinstance(item, str) for item in used_fact_ids)
            or not isinstance(unsupported_claims, tuple)
            or not all(isinstance(item, str) for item in unsupported_claims)
            or _FORBIDDEN_ANSWER_TEXT.search(answer)
        ):
            raise InvalidModelOutput("model.answer_schema_invalid")
        return CandidateAnswer(
            answer=answer,
            used_fact_ids=cast(tuple[str, ...], used_fact_ids),
            unsupported_claims=cast(tuple[str, ...], unsupported_claims),
        )

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.ANSWER_GENERATION,
        task_version="answer-generation-v1",
        input_type=AnswerGenerationTaskInput,
        max_input_bytes=max_input_bytes,
        timeout_ms=timeout_ms,
        max_output_tokens=max_output_tokens,
        build_request=build_request,
        parse_response=parse_response,
    )
    return definition


class DeepSeekAnswerGenerator:
    __slots__ = ("_context", "_definition", "_gateway", "_grounding", "_guard")

    def __init__(
        self,
        *,
        guard: QuestionEgressGuard,
        gateway: StructuredModelGateway,
        context: ModelCallContextAccessor,
        grounding: GroundingPolicyRegistry,
        definition: ModelTaskDefinition[AnswerGenerationTaskInput, CandidateAnswer],
    ) -> None:
        self._guard = guard
        self._gateway = gateway
        self._context = context
        self._grounding = grounding
        self._definition = definition

    async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision:
        question_decision = self._guard.evaluate(input.question)
        if question_decision.disposition is QuestionEgressDisposition.DENIED:
            return _failure(ModelNodeFailureKind.INPUT_DENIED)
        assert question_decision.minimized_question is not None
        try:
            safe_payload = _validate_safe_payload(input.safe_payload)
            policy = self._grounding.require(input.capability_id)
            context = self._context.require_current()
        except ValueError:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        result = await self._gateway.generate(
            definition=self._definition,
            input=AnswerGenerationTaskInput(
                minimized_question=question_decision.minimized_question,
                safe_payload=safe_payload,
            ),
            context=context,
        )
        if result.failure_kind is not None:
            return AnswerGenerationDecision(
                kind=AnswerGenerationDecisionKind.FAILURE,
                failure=to_model_node_failure(result.failure_kind),
            )
        candidate = result.output
        if candidate is None:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        fact_ids = _fact_ids(safe_payload)
        if not set(candidate.used_fact_ids).issubset(fact_ids):
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        try:
            grounding_decision = policy.validate(
                GroundingInput(
                    capability_id=input.capability_id,
                    minimized_question=question_decision.minimized_question,
                    safe_payload=safe_payload,
                    candidate=candidate,
                )
            )
            if not isinstance(grounding_decision, GroundingDecision):
                raise ValueError("model.invalid_grounding_decision")
            accepted = grounding_decision.accepted
        except Exception:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        if not accepted:
            return _failure(ModelNodeFailureKind.INVALID_OUTPUT)
        return AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.ANSWER,
            answer_text=candidate.answer,
        )


def _validate_safe_payload(value: JsonObject) -> JsonObject:
    frozen = freeze_json_object(value, max_bytes=65536, max_depth=8, max_collection_items=256)
    if frozen.get("schema_version") != 1 or isinstance(frozen.get("schema_version"), bool):
        raise InvalidModelOutput("model.safe_payload_invalid")
    facts = frozen.get("facts")
    if not isinstance(facts, tuple) or not facts:
        raise InvalidModelOutput("model.safe_payload_invalid")
    _fact_ids(frozen)
    return frozen


def _fact_ids(payload: JsonObject) -> frozenset[str]:
    facts = payload.get("facts")
    if not isinstance(facts, tuple) or not 1 <= len(facts) <= 256:
        raise InvalidModelOutput("model.safe_payload_invalid")
    result: set[str] = set()
    for fact in facts:
        if not isinstance(fact, Mapping):
            raise InvalidModelOutput("model.safe_payload_invalid")
        fact_id = fact.get("fact_id")
        if not isinstance(fact_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", fact_id):
            raise InvalidModelOutput("model.safe_payload_invalid")
        if fact_id in result:
            raise InvalidModelOutput("model.safe_payload_invalid")
        result.add(fact_id)
    return frozenset(result)


def _failure(kind: ModelNodeFailureKind) -> AnswerGenerationDecision:
    return AnswerGenerationDecision(
        kind=AnswerGenerationDecisionKind.FAILURE,
        failure=ModelNodeFailure(kind=kind),
    )
