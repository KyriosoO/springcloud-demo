from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CancellationSource,
    CapabilityExecutionContext,
    CapabilityResult,
    CapabilityStatus,
    ContractViolation,
    EgressDisposition,
    FailureDetail,
    FailureSource,
    InvalidCapabilityArguments,
    ModelEgressResult,
    OpaqueUserToken,
    SubjectType,
    validate_action_candidate,
    validate_capability_result,
)
from agent_runtime.core.registry import (
    CapabilityRegistryError,
    FrozenCapabilityRegistry,
    InvalidValidatedCall,
    RegisteredCapability,
    ValidatedCapabilityCall,
)
from agent_runtime.settings import CoreRuntimeSettings

_LOGGER = logging.getLogger(__name__)


class ActionLatchState(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    FINISHED = "finished"


class ActionAlreadyClaimed(RuntimeError):
    pass


class InvalidLatchTransition(RuntimeError):
    pass


ActionCompletion = CapabilityStatus | Literal["runtime_cancelled"]


class ActionExecutionLatch:
    __slots__ = ("_capability_id", "_completion", "_lock", "_started_monotonic", "_state")

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._state = ActionLatchState.OPEN
        self._capability_id: str | None = None
        self._started_monotonic: float | None = None
        self._completion: ActionCompletion | None = None

    @property
    def state(self) -> ActionLatchState:
        return self._state

    @property
    def capability_id(self) -> str | None:
        return self._capability_id

    @property
    def completion(self) -> ActionCompletion | None:
        return self._completion

    async def claim(self, capability_id: str) -> None:
        async with self._lock:
            if self._state is not ActionLatchState.OPEN:
                raise ActionAlreadyClaimed("core.second_action_not_allowed")
            self._state = ActionLatchState.CLAIMED
            self._capability_id = capability_id
            self._started_monotonic = asyncio.get_running_loop().time()

    async def finish(self, completion: ActionCompletion) -> None:
        async with self._lock:
            if self._state is not ActionLatchState.CLAIMED:
                raise InvalidLatchTransition("core.invalid_latch_transition")
            self._completion = completion
            self._state = ActionLatchState.FINISHED


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestExecutionScope:
    context: CapabilityExecutionContext
    latch: ActionExecutionLatch = field(default_factory=ActionExecutionLatch)


def _failure_result(
    status: CapabilityStatus,
    code: str,
    source: FailureSource = FailureSource.CORE,
) -> CapabilityResult:
    return CapabilityResult(
        status=status,
        domain_result=None,
        egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        failure=FailureDetail(code=code, source=source),
    )


async def _cancel_and_join(task: asyncio.Task[object]) -> None:
    if not task.done():
        task.cancel()
    with suppress(asyncio.CancelledError):
        try:
            await task
        except Exception:
            # Cancellation/deadline already owns the outcome; a simultaneous
            # losing task exception is deliberately discarded without logging its body.
            pass


def _diagnostic_fingerprint(exc: Exception, stage: str, rule_code: str) -> str:
    exception_type = f"{exc.__class__.__module__}.{exc.__class__.__qualname__}"
    material = f"{exception_type}|{stage}|{rule_code}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:12]


class CapabilityExecutionCore:
    __slots__ = ("_registry", "_settings")

    def __init__(self, registry: FrozenCapabilityRegistry, settings: CoreRuntimeSettings) -> None:
        self._registry = registry
        self._settings = settings

    async def execute(
        self,
        *,
        candidate: ActionCandidate,
        scope: RequestExecutionScope,
    ) -> CapabilityResult:
        context_failure = self._validate_context(scope)
        if context_failure is not None:
            return context_failure

        context = scope.context
        started_monotonic = asyncio.get_running_loop().time()
        if context.cancellation.is_cancelled():
            self._log_rejected(context, None, "core.request_cancelled", started_monotonic)
            return _failure_result(CapabilityStatus.TIMEOUT, "core.request_cancelled")
        loop = asyncio.get_running_loop()
        if loop.time() >= context.deadline_monotonic:
            self._log_rejected(context, None, "core.deadline_exhausted", started_monotonic)
            return _failure_result(CapabilityStatus.TIMEOUT, "core.deadline_exhausted")

        try:
            normalized_candidate = validate_action_candidate(
                candidate,
                max_argument_bytes=self._settings.max_argument_bytes,
                max_json_depth=self._settings.max_json_depth,
                max_collection_items=self._settings.max_collection_items,
            )
        except ContractViolation:
            self._log_rejected(context, None, "core.invalid_candidate", started_monotonic)
            return _failure_result(CapabilityStatus.INVALID_ARGUMENT, "core.invalid_candidate")

        registered = self._registry.resolve(normalized_candidate.capability_id)
        if registered is None:
            self._log_rejected(
                context,
                normalized_candidate.capability_id,
                "core.unsupported_capability",
                started_monotonic,
            )
            return _failure_result(CapabilityStatus.UNSUPPORTED, "core.unsupported_capability")
        try:
            validated_call = registered.validate(normalized_candidate.arguments)
        except InvalidCapabilityArguments:
            self._log_rejected(
                context,
                normalized_candidate.capability_id,
                "core.invalid_arguments",
                started_monotonic,
            )
            return _failure_result(CapabilityStatus.INVALID_ARGUMENT, "core.invalid_arguments")
        except InvalidValidatedCall as exc:
            self._log_invalid(
                context,
                normalized_candidate.capability_id,
                "core.invalid_validated_call",
                exc,
                "validate_arguments",
                started_monotonic,
            )
            return _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.invalid_validated_call")
        except Exception as exc:
            self._log_invalid(
                context,
                normalized_candidate.capability_id,
                "core.validator_exception",
                exc,
                "validate_arguments",
                started_monotonic,
            )
            return _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.validator_exception")

        try:
            await scope.latch.claim(normalized_candidate.capability_id)
        except ActionAlreadyClaimed:
            self._log_rejected(
                context,
                normalized_candidate.capability_id,
                "core.second_action_not_allowed",
                started_monotonic,
            )
            return _failure_result(CapabilityStatus.INVALID_ARGUMENT, "core.second_action_not_allowed")

        try:
            result = await self._invoke_with_budget(registered, validated_call, context)
            try:
                validated_result = validate_capability_result(
                    result,
                    max_domain_result_bytes=self._settings.max_domain_result_bytes,
                    max_model_payload_bytes=self._settings.max_model_payload_bytes,
                    max_json_depth=self._settings.max_json_depth,
                    max_collection_items=self._settings.max_collection_items,
                )
            except (ContractViolation, TypeError, ValueError) as exc:
                self._log_invalid(
                    context,
                    normalized_candidate.capability_id,
                    "core.invalid_result",
                    exc,
                    "validate_result",
                    started_monotonic,
                )
                validated_result = _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.invalid_result")
            await scope.latch.finish(validated_result.status)
            self._log_completed(
                context,
                normalized_candidate.capability_id,
                validated_result,
                started_monotonic,
            )
            return validated_result
        except TimeoutError:
            result = _failure_result(CapabilityStatus.TIMEOUT, "core.handler_timeout")
            await scope.latch.finish(result.status)
            self._log_completed(context, normalized_candidate.capability_id, result, started_monotonic)
            return result
        except _RequestCancelled:
            result = _failure_result(CapabilityStatus.TIMEOUT, "core.request_cancelled")
            await scope.latch.finish(result.status)
            self._log_completed(context, normalized_candidate.capability_id, result, started_monotonic)
            return result
        except _RuntimeShutdown:
            await scope.latch.finish("runtime_cancelled")
            raise asyncio.CancelledError
        except asyncio.CancelledError:
            if scope.latch.state is ActionLatchState.CLAIMED:
                await scope.latch.finish("runtime_cancelled")
            raise
        except (InvalidValidatedCall, CapabilityRegistryError) as exc:
            result = _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.invalid_validated_call")
            await scope.latch.finish(result.status)
            self._log_invalid(
                context,
                normalized_candidate.capability_id,
                "core.invalid_validated_call",
                exc,
                "invoke_handler",
                started_monotonic,
            )
            return result
        except Exception as exc:
            result = _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.handler_exception")
            await scope.latch.finish(result.status)
            self._log_invalid(
                context,
                normalized_candidate.capability_id,
                "core.handler_exception",
                exc,
                "invoke_handler",
                started_monotonic,
            )
            return result

    def _validate_context(self, scope: object) -> CapabilityResult | None:
        if not isinstance(scope, RequestExecutionScope) or not isinstance(scope.context, CapabilityExecutionContext):
            return _failure_result(CapabilityStatus.UNAUTHENTICATED, "core.user_identity_required")
        context = scope.context
        if (
            context.subject_type is not SubjectType.USER
            or not context.subject_id
            or not isinstance(context.user_token, OpaqueUserToken)
        ):
            return _failure_result(CapabilityStatus.UNAUTHENTICATED, "core.user_identity_required")
        if (
            not context.original_question
            or not context.original_question.strip()
            or len(context.original_question) > self._settings.max_question_chars
        ):
            return _failure_result(CapabilityStatus.INVALID_ARGUMENT, "core.invalid_question")
        if not math.isfinite(context.deadline_monotonic):
            return _failure_result(CapabilityStatus.INTERNAL_FAILURE, "core.invalid_execution_context")
        return None

    async def _invoke_with_budget(
        self,
        registered: RegisteredCapability,
        validated_call: ValidatedCapabilityCall,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult:
        loop = asyncio.get_running_loop()
        if context.cancellation.is_cancelled():
            source = await context.cancellation.wait_cancelled()
            if source is CancellationSource.RUNTIME_SHUTDOWN:
                raise _RuntimeShutdown
            raise _RequestCancelled
        if loop.time() >= context.deadline_monotonic:
            raise TimeoutError

        handler_task = asyncio.create_task(registered.invoke(validated_call, context))
        cancellation_task = asyncio.create_task(context.cancellation.wait_cancelled())
        try:
            async with asyncio.timeout_at(context.deadline_monotonic):
                await asyncio.wait(
                    {handler_task, cancellation_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

            if context.cancellation.is_cancelled() or cancellation_task.done():
                source = await cancellation_task
                await _cancel_and_join(handler_task)
                if source is CancellationSource.RUNTIME_SHUTDOWN:
                    raise _RuntimeShutdown
                raise _RequestCancelled
            if loop.time() >= context.deadline_monotonic:
                await _cancel_and_join(handler_task)
                raise TimeoutError
            if not handler_task.done():
                await _cancel_and_join(handler_task)
                raise RuntimeError("core.handler_wait_invariant")
            return await handler_task
        finally:
            if not handler_task.done():
                await _cancel_and_join(handler_task)
            await _cancel_and_join(cancellation_task)

    def _log_rejected(
        self,
        context: CapabilityExecutionContext,
        capability_id: str | None,
        code: str,
        started_monotonic: float,
    ) -> None:
        _LOGGER.info(
            "capability_execution_rejected",
            extra={
                "correlation_id": context.correlation_id,
                "capability_id": capability_id,
                "failure_code": code,
                "duration_ms": max(0.0, (asyncio.get_running_loop().time() - started_monotonic) * 1000),
            },
        )

    def _log_completed(
        self,
        context: CapabilityExecutionContext,
        capability_id: str,
        result: CapabilityResult,
        started_monotonic: float,
    ) -> None:
        _LOGGER.info(
            "capability_execution_completed",
            extra={
                "correlation_id": context.correlation_id,
                "capability_id": capability_id,
                "capability_status": result.status.value,
                "model_egress_allowed": result.egress.disposition is EgressDisposition.ALLOWED,
                "duration_ms": max(0.0, (asyncio.get_running_loop().time() - started_monotonic) * 1000),
            },
        )

    def _log_invalid(
        self,
        context: CapabilityExecutionContext,
        capability_id: str,
        code: str,
        exc: Exception,
        stage: str,
        started_monotonic: float,
    ) -> None:
        _LOGGER.warning(
            "capability_result_invalid",
            extra={
                "correlation_id": context.correlation_id,
                "capability_id": capability_id,
                "failure_code": code,
                "exception_type": f"{exc.__class__.__module__}.{exc.__class__.__qualname__}",
                "diagnostic_fingerprint": _diagnostic_fingerprint(exc, stage, code),
                "duration_ms": max(0.0, (asyncio.get_running_loop().time() - started_monotonic) * 1000),
            },
        )


class _RequestCancelled(Exception):
    pass


class _RuntimeShutdown(Exception):
    pass
