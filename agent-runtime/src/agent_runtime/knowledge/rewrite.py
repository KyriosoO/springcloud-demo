from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass

from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelProviderFailureKind,
    ModelTaskDefinition,
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelGateway,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
    canonical_object_json,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.knowledge.contracts import (
    RewriteCandidate,
    RewriteCandidateSource,
    RewriteMode,
    RewriteResult,
    RewriteStageKind,
    RewriteStageResult,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeRewriteInput:
    minimized_question: str
    max_candidates: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeRewriteOutput:
    candidates: tuple[str, ...]


def _build_request(value: KnowledgeRewriteInput) -> StructuredModelRequest:
    if not 1 <= len(value.minimized_question) <= 4096 or not 1 <= value.max_candidates <= 3:
        raise ValueError("knowledge.rewrite_input_invalid")
    payload = canonical_object_json({"max_candidates": value.max_candidates, "question": value.minimized_question})
    return StructuredModelRequest(
        task_id=ModelTaskId.KNOWLEDGE_REWRITE,
        task_version="1",
        system_instruction=(
            "Return JSON only. Produce retrieval queries that preserve subject, dates, numbers, "
            "negation, document numbers and legal article references. Do not answer the question."
        ),
        user_payload_json=payload,
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=512,
    )


def _parse_response(response: StructuredModelResponse) -> KnowledgeRewriteOutput:
    if response.finish_kind is not StructuredFinishKind.STOP or response.content is None:
        raise InvalidModelOutput("knowledge.invalid_rewrite")
    try:
        value = json.loads(response.content)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise InvalidModelOutput("knowledge.invalid_rewrite") from exc
    if type(value) is not dict or set(value) != {"candidates"} or type(value["candidates"]) is not list:
        raise InvalidModelOutput("knowledge.invalid_rewrite")
    candidates = value["candidates"]
    if not 1 <= len(candidates) <= 3 or any(type(item) is not str or not item or len(item) > 1024 for item in candidates):
        raise InvalidModelOutput("knowledge.invalid_rewrite")
    return KnowledgeRewriteOutput(candidates=tuple(candidates))


class KnowledgeRewriteTaskV1:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeRewriteInput, KnowledgeRewriteOutput]:
        return ModelTaskDefinition(
            task_id=ModelTaskId.KNOWLEDGE_REWRITE,
            task_version="1",
            input_type=KnowledgeRewriteInput,
            max_input_bytes=16384,
            timeout_ms=8000,
            max_output_tokens=512,
            build_request=_build_request,
            parse_response=_parse_response,
        )


class KnowledgeQuestionRewriter:
    __slots__ = ("_allow_fallback", "_context", "_definition", "_gateway", "_guard", "_max_candidates", "_max_chars", "_semantic")

    def __init__(
        self,
        *,
        guard: QuestionEgressGuard,
        semantic_guard: QuestionSemanticGuard,
        gateway: StructuredModelGateway,
        context: ModelCallContextAccessor,
        definition: ModelTaskDefinition[KnowledgeRewriteInput, KnowledgeRewriteOutput],
        max_candidates: int,
        max_retrieval_query_chars: int,
        allow_original_fallback: bool,
    ) -> None:
        self._guard = guard
        self._semantic = semantic_guard
        self._gateway = gateway
        self._context = context
        self._definition = definition
        self._max_candidates = max_candidates
        self._max_chars = max_retrieval_query_chars
        self._allow_fallback = allow_original_fallback

    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult:
        del timeout_s
        try:
            constraints = self._semantic.extract(original_question)
        except KnowledgeInputError:
            return RewriteStageResult(kind=RewriteStageKind.INPUT_INVALID)
        decision = self._guard.evaluate(original_question)
        normalized = unicodedata.normalize("NFC", " ".join(original_question.strip().split()))
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return self._fallback(
                original_question=original_question,
                normalized=normalized,
                constraints=constraints,
                policy_version=decision.policy_version,
                denied=True,
                denied_reason=decision.reason_code.value if decision.reason_code is not None else "unknown_input",
            )
        try:
            context = self._context.require_current()
        except Exception:
            return RewriteStageResult(kind=RewriteStageKind.FAILURE)
        assert decision.minimized_question is not None
        result = await self._gateway.generate(
            definition=self._definition,
            input=KnowledgeRewriteInput(
                minimized_question=decision.minimized_question,
                max_candidates=self._max_candidates,
            ),
            context=context,
        )
        if result.output is not None:
            accepted: list[RewriteCandidate] = []
            seen: set[str] = set()
            for ordinal, raw in enumerate(result.output.candidates, 1):
                candidate = unicodedata.normalize("NFC", " ".join(raw.strip().split()))
                if candidate in seen:
                    continue
                seen.add(candidate)
                validation = self._semantic.validate_candidate(
                    candidate=candidate,
                    constraints=constraints,
                    max_chars=self._max_chars,
                )
                if validation.accepted:
                    accepted.append(RewriteCandidate(text=candidate, source=RewriteCandidateSource.MODEL, ordinal=ordinal))
            if accepted:
                return RewriteStageResult(
                    kind=RewriteStageKind.SUCCESS,
                    rewrite=RewriteResult(
                        original_question=original_question,
                        selected_query=accepted[0].text,
                        candidates=tuple(accepted),
                        mode=RewriteMode.MODEL,
                        question_policy_version=decision.policy_version,
                        question_egress_denied=False,
                    ),
                )
        failure = result.failure_kind
        fallback = self._fallback(
            original_question=original_question,
            normalized=normalized,
            constraints=constraints,
            policy_version=decision.policy_version,
            denied=False,
            denied_reason=None,
        )
        if fallback.kind is RewriteStageKind.SUCCESS:
            return fallback
        if failure is ModelProviderFailureKind.PROVIDER_TIMEOUT:
            return RewriteStageResult(kind=RewriteStageKind.TIMEOUT)
        return RewriteStageResult(kind=RewriteStageKind.FAILURE)

    def _fallback(
        self,
        *,
        original_question: str,
        normalized: str,
        constraints: object,
        policy_version: str,
        denied: bool,
        denied_reason: str | None,
    ) -> RewriteStageResult:
        from typing import cast
        from agent_runtime.knowledge.contracts import ProtectedConstraintSet

        if self._allow_fallback and self._semantic.validate_candidate(
            candidate=normalized,
            constraints=cast(ProtectedConstraintSet, constraints),
            max_chars=self._max_chars,
        ).accepted:
            candidate = RewriteCandidate(text=normalized, source=RewriteCandidateSource.ORIGINAL_FALLBACK, ordinal=1)
            return RewriteStageResult(
                kind=RewriteStageKind.SUCCESS,
                rewrite=RewriteResult(
                    original_question=original_question,
                    selected_query=normalized,
                    candidates=(candidate,),
                    mode=RewriteMode.ORIGINAL_FALLBACK,
                    question_policy_version=policy_version,
                    question_egress_denied=denied,
                ),
            )
        if denied:
            return RewriteStageResult(
                kind=RewriteStageKind.QUESTION_DENIED,
                policy_version=policy_version,
                reason_code=denied_reason,
            )
        return RewriteStageResult(kind=RewriteStageKind.FAILURE)

