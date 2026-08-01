from __future__ import annotations

import asyncio
from typing import Any, Generic, TypeVar

from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    FailureDetail,
    FailureSource,
    ModelEgressResult,
)
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessFailureResult,
    BusinessHttpClient,
    BusinessNoResult,
    BusinessProjectionError,
    BusinessRecordsResult,
    BusinessServiceFailureKind,
    BusinessTransportFailure,
    BusinessTransportFailureKind,
    InvalidBusinessArguments,
    InvalidBusinessWireResponse,
)
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.result_mapping import map_business_http_status
from agent_runtime.business.settings import GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector

TInput = TypeVar("TInput")
TWireRequest = TypeVar("TWireRequest")
TWireResponse = TypeVar("TWireResponse")
TRecord = TypeVar("TRecord")


def _failure(status: CapabilityStatus, code: str, source: FailureSource) -> CapabilityResult:
    return CapabilityResult(
        status=status,
        domain_result=None,
        egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        failure=FailureDetail(code=code, source=source),
    )


class BoundBusinessActionHandler(Generic[TInput, TWireRequest, TWireResponse, TRecord]):
    __slots__ = ("_client", "_definition", "_egress", "_max_user_bytes", "_policy", "_settings", "_snapshot_id", "_user")

    def __init__(
        self,
        *,
        definition: BusinessActionDefinition[TInput, TWireRequest, TWireResponse, TRecord],
        settings: BusinessActionSettings,
        client: BusinessHttpClient,
        user_projector: BusinessUserResultProjector,
        egress_projector: BusinessEgressProjector,
        egress_policy: GlobalBusinessEgressPolicy,
        config_snapshot_id: str,
        max_user_result_bytes: int,
    ) -> None:
        self._definition = definition
        self._settings = settings
        self._client = client
        self._user = user_projector
        self._egress = egress_projector
        self._policy = egress_policy
        self._snapshot_id = config_snapshot_id
        self._max_user_bytes = max_user_result_bytes

    async def handle(self, input: TInput, context: CapabilityExecutionContext) -> CapabilityResult:
        if context.cancellation.is_cancelled():
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        loop = asyncio.get_running_loop()
        call_deadline = min(context.deadline_monotonic, loop.time() + self._settings.timeout_ms / 1000)
        if call_deadline - loop.time() <= 0.1:
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        try:
            wire_request = self._definition.request_mapper.map(input, self._settings)
        except InvalidBusinessArguments:
            return _failure(CapabilityStatus.INVALID_ARGUMENT, "business.invalid_arguments", FailureSource.CAPABILITY)
        request = self._definition.wire_codec.encode(wire_request)
        try:
            response = await self._client.execute(
                request=request,
                user_token=context.user_token,
                call_deadline=call_deadline,
                cancellation=context.cancellation,
            )
        except asyncio.CancelledError:
            raise
        except BusinessTransportFailure as exc:
            if exc.kind is BusinessTransportFailureKind.TIMEOUT:
                return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
            if exc.kind is BusinessTransportFailureKind.RESPONSE_TOO_LARGE:
                return _failure(CapabilityStatus.DOWNSTREAM_FAILURE, "business.invalid_response", FailureSource.DOWNSTREAM)
            return _failure(CapabilityStatus.DOWNSTREAM_FAILURE, "business.downstream_failure", FailureSource.DOWNSTREAM)
        if self._expired(context, call_deadline):
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        mapped_result = map_business_http_status(response, self._definition.http_status_semantics)
        if mapped_result is None:
            try:
                wire_response = self._definition.wire_codec.decode_success(request=wire_request, response=response)
                service_result = self._definition.response_normalizer.normalize_success(wire_response)
            except InvalidBusinessWireResponse:
                return _failure(CapabilityStatus.DOWNSTREAM_FAILURE, "business.invalid_response", FailureSource.DOWNSTREAM)
        else:
            service_result = mapped_result
        if self._expired(context, call_deadline):
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        if isinstance(service_result, BusinessNoResult):
            return CapabilityResult(
                status=CapabilityStatus.NO_RESULT,
                domain_result=None,
                egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
                failure=None,
            )
        if isinstance(service_result, BusinessFailureResult):
            return self._map_failure(service_result.kind)
        try:
            user_result = self._user.project(
                definition=self._definition,
                settings=self._settings,
                result=service_result,
                max_user_result_bytes=self._max_user_bytes,
            )
        except BusinessProjectionError as exc:
            code = str(exc)
            if code not in {"business.minimum_user_result_not_met", "business.user_result_too_large"}:
                code = "business.minimum_user_result_not_met"
            return _failure(CapabilityStatus.DOWNSTREAM_FAILURE, code, FailureSource.CAPABILITY)
        if self._expired(context, call_deadline):
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        egress = self._egress.project(
            definition=self._definition,
            settings=self._settings,
            user_result=user_result,
            policy=self._policy,
            config_snapshot_id=self._snapshot_id,
        )
        if self._expired(context, call_deadline):
            return _failure(CapabilityStatus.TIMEOUT, "business.downstream_timeout", FailureSource.DOWNSTREAM)
        return CapabilityResult(
            status=CapabilityStatus.SUCCESS,
            domain_result=user_result.to_domain_result(),
            egress=egress,
            failure=None,
        )

    @staticmethod
    def _expired(context: CapabilityExecutionContext, call_deadline: float) -> bool:
        return context.cancellation.is_cancelled() or asyncio.get_running_loop().time() >= call_deadline

    @staticmethod
    def _map_failure(kind: BusinessServiceFailureKind) -> CapabilityResult:
        mapping = {
            BusinessServiceFailureKind.INVALID_ARGUMENT: (CapabilityStatus.INVALID_ARGUMENT, "business.invalid_arguments"),
            BusinessServiceFailureKind.UNAUTHENTICATED: (CapabilityStatus.UNAUTHENTICATED, "business.downstream_unauthenticated"),
            BusinessServiceFailureKind.FORBIDDEN: (CapabilityStatus.FORBIDDEN, "business.downstream_forbidden"),
            BusinessServiceFailureKind.TIMEOUT: (CapabilityStatus.TIMEOUT, "business.downstream_timeout"),
            BusinessServiceFailureKind.RATE_LIMITED: (CapabilityStatus.DOWNSTREAM_FAILURE, "business.rate_limited"),
            BusinessServiceFailureKind.INVALID_RESPONSE: (CapabilityStatus.DOWNSTREAM_FAILURE, "business.invalid_response"),
            BusinessServiceFailureKind.UNAVAILABLE: (CapabilityStatus.DOWNSTREAM_FAILURE, "business.downstream_failure"),
        }
        status, code = mapping[kind]
        return _failure(status, code, FailureSource.DOWNSTREAM)
