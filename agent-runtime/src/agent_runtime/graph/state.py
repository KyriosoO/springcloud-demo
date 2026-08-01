from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CapabilityDescriptor,
    CapabilityResult,
    CapabilityStatus,
    FailureDetail,
    JsonObject,
)
from agent_runtime.core.execution import RequestExecutionScope


class AgentInputState(TypedDict):
    question: str


class AgentRequestState(AgentInputState, total=False):
    action_candidate: ActionCandidate
    capability_result: CapabilityResult
    final_outcome: "AgentSemanticOutcome"


class AgentOutputState(TypedDict):
    final_outcome: "AgentSemanticOutcome"


class ActionCandidateStateUpdate(TypedDict, total=False):
    action_candidate: ActionCandidate
    final_outcome: "AgentSemanticOutcome"


class CapabilityExecutionStateUpdate(TypedDict):
    capability_result: CapabilityResult


class FinalOutcomeStateUpdate(TypedDict):
    final_outcome: "AgentSemanticOutcome"


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphRunContext:
    execution_scope: RequestExecutionScope


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentSemanticOutcome:
    status: CapabilityStatus
    capability_id: str | None
    answer_text: str | None
    user_result: JsonObject | None
    failure: FailureDetail | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionSelectionInput:
    question: str
    descriptors: tuple[CapabilityDescriptor, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerGenerationInput:
    question: str
    capability_id: str
    safe_payload: JsonObject


class ModelNodeFailureKind(StrEnum):
    INPUT_DENIED = "input_denied"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_FAILURE = "provider_failure"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelNodeFailure:
    kind: ModelNodeFailureKind


class ActionSelectionDecisionKind(StrEnum):
    CANDIDATE = "candidate"
    UNSUPPORTED = "unsupported"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionSelectionDecision:
    kind: ActionSelectionDecisionKind
    candidate: ActionCandidate | None = None
    failure: ModelNodeFailure | None = None

    def __post_init__(self) -> None:
        valid = (
            (self.kind is ActionSelectionDecisionKind.CANDIDATE and self.candidate is not None and self.failure is None)
            or (self.kind is ActionSelectionDecisionKind.UNSUPPORTED and self.candidate is None and self.failure is None)
            or (self.kind is ActionSelectionDecisionKind.FAILURE and self.candidate is None and self.failure is not None)
        )
        if not valid:
            raise ValueError("core.invalid_model_node_decision")


class AnswerGenerationDecisionKind(StrEnum):
    ANSWER = "answer"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerGenerationDecision:
    kind: AnswerGenerationDecisionKind
    answer_text: str | None = None
    failure: ModelNodeFailure | None = None

    def __post_init__(self) -> None:
        valid = (
            (
                self.kind is AnswerGenerationDecisionKind.ANSWER
                and isinstance(self.answer_text, str)
                and bool(self.answer_text.strip())
                and self.failure is None
            )
            or (
                self.kind is AnswerGenerationDecisionKind.FAILURE
                and self.answer_text is None
                and self.failure is not None
            )
        )
        if not valid:
            raise ValueError("core.invalid_model_node_decision")
