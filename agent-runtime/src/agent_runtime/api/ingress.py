from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from starlette.requests import Request

from agent_runtime.api.cancellation import MutableCancellationSignal, watch_disconnect
from agent_runtime.api.errors import RuntimeProtocolViolation, RuntimeVersionConflict
from agent_runtime.api.limits import RuntimeRequestLimiter
from agent_runtime.api.models import (
    FailureResponse,
    ObservedDownstreamCall,
    ObservedModelCall,
    ObservedPlan,
    RuntimeInspectResponse,
    RuntimeInvokeRequest,
    RuntimeInvokeResponse,
)
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityStatus,
    FailureDetail,
    FailureSource,
    OpaqueUserToken,
    SubjectType,
)
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.observation import observation_scope

_LOGGER = logging.getLogger(__name__)


class RuntimeInvoker(Protocol):
    async def ainvoke(
        self,
        *,
        question: str,
        scope: RequestExecutionScope,
    ) -> AgentSemanticOutcome: ...


class RuntimeClocks(Protocol):
    def epoch_ms(self) -> int: ...

    def monotonic(self) -> float: ...


@dataclass(frozen=True, slots=True)
class SystemRuntimeClocks:
    def epoch_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def monotonic(self) -> float:
        return time.monotonic()


def _extract_raw_token(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise RuntimeProtocolViolation
    raw = authorization[7:]
    if not raw or len(raw.encode("utf-8")) > 16384:
        raise RuntimeProtocolViolation
    return raw


def _to_plain_json(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_plain_json(item) for item in value]
    return value


def _timeout_outcome() -> AgentSemanticOutcome:
    return AgentSemanticOutcome(
        status=CapabilityStatus.TIMEOUT,
        capability_id=None,
        answer_text="查询超时。",
        user_result=None,
        failure=FailureDetail(code="core.deadline_exhausted", source=FailureSource.CORE),
    )


def to_execution_scope(
    payload: RuntimeInvokeRequest,
    raw_token: str,
    cancellation: MutableCancellationSignal,
    clocks: RuntimeClocks,
) -> RequestExecutionScope | None:
    effective_remaining_ms = min(
        payload.remaining_timeout_ms,
        payload.deadline_epoch_ms - clocks.epoch_ms(),
    )
    if effective_remaining_ms <= 100:
        return None
    deadline_monotonic = clocks.monotonic() + (effective_remaining_ms - 100) / 1000
    return RequestExecutionScope(
        context=CapabilityExecutionContext(
            request_id=payload.request_id,
            correlation_id=payload.correlation_id,
            original_question=payload.question,
            subject_id=payload.subject.id,
            subject_type=SubjectType.USER,
            user_token=OpaqueUserToken.from_raw(raw_token),
            deadline_monotonic=deadline_monotonic,
            cancellation=cancellation,
        )
    )


def _response_from_outcome(
    request_id: str,
    outcome: AgentSemanticOutcome,
) -> RuntimeInvokeResponse:
    failure = None
    if outcome.failure is not None:
        failure = FailureResponse(code=outcome.failure.code, source=outcome.failure.source)
    user_result = None
    if outcome.user_result is not None:
        plain = _to_plain_json(outcome.user_result)
        if not isinstance(plain, dict):
            raise RuntimeError("runtime.user_result_invalid")
        user_result = plain
    return RuntimeInvokeResponse(
        contractVersion=1,
        requestId=request_id,
        status=outcome.status,
        capabilityId=outcome.capability_id,
        answerText=outcome.answer_text,
        userResult=user_result,
        failure=failure,
    )


async def invoke_agent(
    request: Request,
    payload: RuntimeInvokeRequest,
    authorization: str,
    x_agent_contract_version: str,
    runtime: RuntimeInvoker,
    limiter: RuntimeRequestLimiter,
    *,
    clocks: RuntimeClocks | None = None,
    disconnect_poll_s: float = 0.1,
) -> RuntimeInvokeResponse:
    if x_agent_contract_version != "1":
        if x_agent_contract_version.isdigit():
            raise RuntimeVersionConflict
        raise RuntimeProtocolViolation
    if payload.contract_version != int(x_agent_contract_version):
        raise RuntimeVersionConflict
    raw_token = _extract_raw_token(authorization)
    lease = await limiter.try_acquire()
    signal = MutableCancellationSignal()
    watcher: asyncio.Task[None] | None = None
    active_clocks = clocks or SystemRuntimeClocks()
    started = active_clocks.monotonic()
    completed_status: CapabilityStatus | None = None
    try:
        scope = to_execution_scope(payload, raw_token, signal, active_clocks)
        if scope is None:
            response = _response_from_outcome(payload.request_id, _timeout_outcome())
            completed_status = response.status
            return response
        watcher = asyncio.create_task(
            watch_disconnect(request, signal, disconnect_poll_s),
            name=f"disconnect:{payload.request_id}",
        )
        outcome = await runtime.ainvoke(question=payload.question, scope=scope)
        response = _response_from_outcome(payload.request_id, outcome)
        completed_status = response.status
        return response
    finally:
        if watcher is not None:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
        await lease.release()
        _LOGGER.info(
            "runtime_invoke_completed",
            extra={
                "request_id": payload.request_id,
                "correlation_id": payload.correlation_id,
                "status": completed_status.value if completed_status is not None else "cancelled",
                "duration_ms": max(0.0, (active_clocks.monotonic() - started) * 1000),
            },
        )


async def inspect_agent(
    request: Request,
    payload: RuntimeInvokeRequest,
    authorization: str,
    x_agent_contract_version: str,
    runtime: RuntimeInvoker,
    limiter: RuntimeRequestLimiter,
    *,
    clocks: RuntimeClocks | None = None,
    disconnect_poll_s: float = 0.1,
) -> RuntimeInspectResponse:
    with observation_scope() as collector:
        response = await invoke_agent(
            request,
            payload,
            authorization,
            x_agent_contract_version,
            runtime,
            limiter,
            clocks=clocks,
            disconnect_poll_s=disconnect_poll_s,
        )
        snapshot = collector.snapshot()
    return RuntimeInspectResponse(
        contractVersion=response.contract_version,
        requestId=response.request_id,
        status=response.status,
        capabilityId=response.capability_id,
        answerText=response.answer_text,
        userResult=response.user_result,
        failure=response.failure,
        modelCalls=tuple(ObservedModelCall.model_validate(item) for item in snapshot.model_calls),
        plans=tuple(ObservedPlan.model_validate(item) for item in snapshot.plans),
        downstreamCalls=tuple(
            ObservedDownstreamCall.model_validate(item) for item in snapshot.downstream_calls
        ),
    )
