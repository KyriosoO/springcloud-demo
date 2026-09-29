"""Request-local intent stage for the sole minimal Knowledge production binding."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent_runtime.knowledge.intent_contracts import KnowledgeQueryIntent, KnowledgeQueryIntentInput
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelProviderFailureKind, ModelTaskDefinition, QuestionEgressDisposition,
    QuestionEgressReasonCode, StructuredModelGateway,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


class MinimalIntentStageKind(StrEnum):
    SUCCESS = "success"
    INPUT_INVALID = "input_invalid"
    QUESTION_DENIED = "question_denied"
    TIMEOUT = "timeout"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class MinimalIntentStageResult:
    kind: MinimalIntentStageKind
    question: KnowledgeQueryIntentInput | None = None
    intent: KnowledgeQueryIntent | None = None
    policy_version: str | None = None


class MinimalKnowledgeIntentStage:
    def __init__(
        self, *, gateway: StructuredModelGateway, context: ModelCallContextAccessor,
        definition: ModelTaskDefinition[KnowledgeQueryIntentInput, KnowledgeQueryIntent],
        enabled_domain_ids: tuple[str, ...], max_query_chars: int = 1024,
    ) -> None:
        if definition.task_version != "12" or definition.input_type is not KnowledgeQueryIntentInput:
            raise ValueError("knowledge.production_task_version_invalid")
        if type(max_query_chars) is not int or not 128 <= max_query_chars <= 1024:
            raise ValueError("knowledge.invalid_query_limit")
        self._gateway = gateway
        self._context = context
        self._definition = definition
        self._domains = enabled_domain_ids
        self._max_query_chars = max_query_chars
        self._guard = QuestionEgressGuard()

    async def rewrite(self, *, original_question: str, timeout_s: float) -> MinimalIntentStageResult:
        del timeout_s  # The Capability deadline and model task already bound the call.
        decision = self._guard.evaluate(original_question)
        if decision.disposition is not QuestionEgressDisposition.ALLOWED:
            kind = (MinimalIntentStageKind.INPUT_INVALID
                    if decision.reason_code is QuestionEgressReasonCode.INVALID_QUESTION
                    else MinimalIntentStageKind.QUESTION_DENIED)
            return MinimalIntentStageResult(kind=kind, policy_version=decision.policy_version)
        assert decision.minimized_question is not None
        if len(decision.minimized_question) > self._max_query_chars:
            return MinimalIntentStageResult(kind=MinimalIntentStageKind.INPUT_INVALID)
        question = KnowledgeQueryIntentInput(minimized_question=decision.minimized_question)
        try:
            response = await self._gateway.generate(
                definition=self._definition, input=question, context=self._context.require_current(),
            )
        except TimeoutError:
            return MinimalIntentStageResult(kind=MinimalIntentStageKind.TIMEOUT)
        except Exception:
            return MinimalIntentStageResult(kind=MinimalIntentStageKind.FAILURE)
        if response.output is None:
            kind = (MinimalIntentStageKind.TIMEOUT
                    if response.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
                    else MinimalIntentStageKind.FAILURE)
            return MinimalIntentStageResult(kind=kind)
        intent = response.output
        if (type(intent) is not KnowledgeQueryIntent
                or tuple(domain for domain in self._domains if domain in intent.selected_domain_ids)
                    != intent.selected_domain_ids):
            return MinimalIntentStageResult(kind=MinimalIntentStageKind.FAILURE)
        return MinimalIntentStageResult(kind=MinimalIntentStageKind.SUCCESS, question=question,
                                        intent=intent, policy_version=decision.policy_version)
