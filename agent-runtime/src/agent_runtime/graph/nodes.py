from __future__ import annotations

from typing import Literal, Protocol

from langgraph.runtime import Runtime

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    FailureDetail,
    FailureSource,
    ModelEgressResult,
)
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.graph.state import (
    ActionCandidateStateUpdate,
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ActionSelectionInvalidCode,
    AgentInputState,
    AgentRequestState,
    AgentSemanticOutcome,
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    CapabilityExecutionStateUpdate,
    FinalOutcomeStateUpdate,
    GraphRunContext,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.capability_api.contracts import CapabilityDescriptor
from agent_runtime.graph.action_resolution import InvalidActionResolution
from agent_runtime.graph.business_query_planning import BusinessPlanningDecision


class ActionSelectionNode(Protocol):
    async def __call__(
        self,
        input: ActionSelectionInput,
    ) -> ActionSelectionDecision | BusinessPlanningDecision: ...


class AnswerGenerationNode(Protocol):
    async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision: ...


_FIXED_TEXT = {
    CapabilityStatus.SUCCESS: "查询已完成。",
    CapabilityStatus.NO_RESULT: "未找到符合条件的结果。",
    CapabilityStatus.UNSUPPORTED: "当前不支持该查询。",
    CapabilityStatus.INVALID_ARGUMENT: "查询参数无效。",
    CapabilityStatus.UNAUTHENTICATED: "用户身份无效。",
    CapabilityStatus.FORBIDDEN: "没有权限执行该查询。",
    CapabilityStatus.TIMEOUT: "查询超时。",
    CapabilityStatus.DOWNSTREAM_FAILURE: "下游查询暂时不可用。",
    CapabilityStatus.MODEL_EGRESS_DENIED: "当前结果不能用于生成回答。",
    CapabilityStatus.INTERNAL_FAILURE: "查询处理失败。",
}


def _failure_outcome(
    status: CapabilityStatus,
    code: str,
    source: FailureSource,
    *,
    capability_id: str | None = None,
) -> AgentSemanticOutcome:
    return AgentSemanticOutcome(
        status=status,
        capability_id=capability_id,
        answer_text=_FIXED_TEXT[status],
        user_result=None,
        failure=FailureDetail(code=code, source=source),
    )


def _map_model_failure(
    failure: ModelNodeFailure,
    *,
    capability_id: str | None,
) -> AgentSemanticOutcome:
    mapping = {
        ModelNodeFailureKind.INPUT_DENIED: (
            CapabilityStatus.MODEL_EGRESS_DENIED,
            "model.input_denied",
            FailureSource.POLICY,
        ),
        ModelNodeFailureKind.PROVIDER_TIMEOUT: (
            CapabilityStatus.TIMEOUT,
            "model.provider_timeout",
            FailureSource.DOWNSTREAM,
        ),
        ModelNodeFailureKind.PROVIDER_FAILURE: (
            CapabilityStatus.DOWNSTREAM_FAILURE,
            "model.provider_failure",
            FailureSource.DOWNSTREAM,
        ),
        ModelNodeFailureKind.INVALID_OUTPUT: (
            CapabilityStatus.DOWNSTREAM_FAILURE,
            "model.invalid_output",
            FailureSource.DOWNSTREAM,
        ),
    }
    values = mapping.get(failure.kind)
    if values is None:
        return _failure_outcome(
            CapabilityStatus.INTERNAL_FAILURE,
            "core.invalid_model_node_decision",
            FailureSource.CORE,
            capability_id=capability_id,
        )
    status, code, source = values
    return _failure_outcome(status, code, source, capability_id=capability_id)


async def select_action_node(
    state: AgentInputState,
    runtime: Runtime[GraphRunContext] | None = None,
    *,
    descriptors: tuple[CapabilityDescriptor, ...],
    selector: ActionSelectionNode,
) -> ActionCandidateStateUpdate:
    if not descriptors:
        return {
            "final_outcome": _failure_outcome(
                CapabilityStatus.UNSUPPORTED,
                "core.no_enabled_capability",
                FailureSource.CORE,
            )
        }
    try:
        decision = await selector(ActionSelectionInput(
            question=state["question"],
            descriptors=descriptors,
            cancellation=(
                runtime.context.execution_scope.context.cancellation
                if runtime is not None
                else None
            ),
        ))
    except InvalidActionResolution:
        return {
            "final_outcome": _failure_outcome(
                CapabilityStatus.INTERNAL_FAILURE,
                "core.invalid_action_resolution",
                FailureSource.CORE,
            )
        }
    if isinstance(decision, BusinessPlanningDecision):
        if decision.candidate is not None:
            return {"action_candidate": decision.candidate}
        assert decision.status is not None and decision.failure_code is not None
        source = (
            FailureSource.POLICY
            if decision.status in {
                CapabilityStatus.FORBIDDEN,
                CapabilityStatus.MODEL_EGRESS_DENIED,
            }
            else FailureSource.DOWNSTREAM
            if decision.status in {CapabilityStatus.TIMEOUT, CapabilityStatus.DOWNSTREAM_FAILURE}
            else FailureSource.CORE
        )
        return {
            "final_outcome": _failure_outcome(
                decision.status,
                decision.failure_code,
                source,
            )
        }
    if isinstance(decision, ActionSelectionDecision):
        if decision.kind is ActionSelectionDecisionKind.CANDIDATE and decision.candidate is not None:
            return {"action_candidate": decision.candidate}
        if decision.kind is ActionSelectionDecisionKind.UNSUPPORTED:
            return {
                "final_outcome": _failure_outcome(
                    CapabilityStatus.UNSUPPORTED,
                    "core.no_supported_capability_candidate",
                    FailureSource.CORE,
                )
            }
        if (
            decision.kind is ActionSelectionDecisionKind.INVALID_ARGUMENT
            and isinstance(decision.invalid_code, ActionSelectionInvalidCode)
        ):
            return {
                "final_outcome": _failure_outcome(
                    CapabilityStatus.INVALID_ARGUMENT,
                    decision.invalid_code.value,
                    FailureSource.CORE,
                )
            }
        if decision.kind is ActionSelectionDecisionKind.FAILURE and decision.failure is not None:
            return {"final_outcome": _map_model_failure(decision.failure, capability_id=None)}
    return {
        "final_outcome": _failure_outcome(
            CapabilityStatus.INTERNAL_FAILURE,
            "core.invalid_model_node_decision",
            FailureSource.CORE,
        )
    }


def route_after_selection(state: AgentRequestState) -> Literal["execute", "end"]:
    return "end" if "final_outcome" in state else "execute"


async def execute_capability_node(
    state: AgentRequestState,
    runtime: Runtime[GraphRunContext],
    *,
    core: CapabilityExecutionCore,
) -> CapabilityExecutionStateUpdate:
    candidate = state.get("action_candidate")
    if candidate is None:
        return {
            "capability_result": CapabilityResult(
                status=CapabilityStatus.INTERNAL_FAILURE,
                domain_result=None,
                egress=_not_applicable_egress(),
                failure=FailureDetail(code="core.invalid_graph_state", source=FailureSource.CORE),
            )
        }
    result = await core.execute(candidate=candidate, scope=runtime.context.execution_scope)
    return {"capability_result": result}


def route_after_capability(state: AgentRequestState) -> Literal["answer", "fixed"]:
    result = state.get("capability_result")
    if (
        result is not None
        and result.status is CapabilityStatus.SUCCESS
        and result.egress.disposition is EgressDisposition.ALLOWED
        and result.egress.safe_payload
    ):
        return "answer"
    return "fixed"


async def generate_answer_node(
    state: AgentRequestState,
    *,
    answer_generator: AnswerGenerationNode,
) -> FinalOutcomeStateUpdate:
    candidate = state.get("action_candidate")
    result = state.get("capability_result")
    if (
        candidate is None
        or result is None
        or result.status is not CapabilityStatus.SUCCESS
        or result.egress.disposition is not EgressDisposition.ALLOWED
        or result.egress.safe_payload is None
    ):
        return {
            "final_outcome": _failure_outcome(
                CapabilityStatus.INTERNAL_FAILURE,
                "core.invalid_graph_state",
                FailureSource.CORE,
                capability_id=candidate.capability_id if candidate else None,
            )
        }
    decision = await answer_generator(
        AnswerGenerationInput(
            question=state["question"],
            capability_id=candidate.capability_id,
            safe_payload=result.egress.safe_payload,
        )
    )
    if isinstance(decision, AnswerGenerationDecision):
        if decision.kind is AnswerGenerationDecisionKind.ANSWER and decision.answer_text is not None:
            return {
                "final_outcome": AgentSemanticOutcome(
                    status=CapabilityStatus.SUCCESS,
                    capability_id=candidate.capability_id,
                    answer_text=decision.answer_text,
                    user_result=None,
                    failure=None,
                )
            }
        if decision.kind is AnswerGenerationDecisionKind.FAILURE and decision.failure is not None:
            return {
                "final_outcome": _map_model_failure(
                    decision.failure,
                    capability_id=candidate.capability_id,
                )
            }
    return {
        "final_outcome": _failure_outcome(
            CapabilityStatus.INTERNAL_FAILURE,
            "core.invalid_model_node_decision",
            FailureSource.CORE,
            capability_id=candidate.capability_id,
        )
    }


def finalize_without_model(state: AgentRequestState) -> FinalOutcomeStateUpdate:
    candidate = state.get("action_candidate")
    result = state.get("capability_result")
    capability_id = candidate.capability_id if candidate is not None else None
    if result is None:
        return {
            "final_outcome": _failure_outcome(
                CapabilityStatus.INTERNAL_FAILURE,
                "core.invalid_graph_state",
                FailureSource.CORE,
                capability_id=capability_id,
            )
        }

    if result.status is CapabilityStatus.SUCCESS and result.egress.disposition in (
        EgressDisposition.DENIED,
        EgressDisposition.NOT_APPLICABLE,
    ):
        return {
            "final_outcome": AgentSemanticOutcome(
                status=result.status,
                capability_id=capability_id,
                answer_text=_FIXED_TEXT[result.status],
                user_result=result.domain_result,
                failure=None,
            )
        }
    if result.status is CapabilityStatus.NO_RESULT and result.egress.disposition is EgressDisposition.NOT_APPLICABLE:
        text = _FIXED_TEXT[result.status]
        if capability_id == "knowledge.query" and result.domain_result is not None:
            reason = result.domain_result.get("reason")
            if reason == "insufficient_evidence":
                text = "已检索到资料，但不足以完整回答此问题。"
            elif reason == "clarification_required":
                text = "查询条件不足，请补充适用期间、纳税人类型或计税方法等必要条件。"
        return {
            "final_outcome": AgentSemanticOutcome(
                status=result.status,
                capability_id=capability_id,
                answer_text=text,
                user_result=result.domain_result,
                failure=None,
            )
        }
    if result.status is CapabilityStatus.MODEL_EGRESS_DENIED and result.egress.disposition is EgressDisposition.DENIED:
        return {
            "final_outcome": AgentSemanticOutcome(
                status=result.status,
                capability_id=capability_id,
                answer_text=_FIXED_TEXT[result.status],
                user_result=None,
                failure=result.failure,
            )
        }
    if result.failure is not None and result.status not in (CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT):
        return {
            "final_outcome": AgentSemanticOutcome(
                status=result.status,
                capability_id=capability_id,
                answer_text=_FIXED_TEXT[result.status],
                user_result=None,
                failure=result.failure,
            )
        }
    return {
        "final_outcome": _failure_outcome(
            CapabilityStatus.INTERNAL_FAILURE,
            "core.invalid_result",
            FailureSource.CORE,
            capability_id=capability_id,
        )
    }


def _not_applicable_egress() -> ModelEgressResult:
    return ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE)
