from __future__ import annotations

import asyncio
import functools
import json
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest

from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.contracts import BusinessHttpRequest
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityStatus,
    EgressDisposition,
    OpaqueUserToken,
    SubjectType,
)
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.transaction.evidence_contract import validate_probe_evidence

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TRANSACTION_LIVE") != "1",
    reason="requires explicit controlled Transaction live opt-in",
)

_SAFE_CASE_IDS = frozenset(
    {"adminPrimary", "adminSecondary", "viewer", "unknownRole", "missingToken", "malformedToken", "serviceToken"}
)
_SAFE_CODES = frozenset(
    {
        "transaction.live_case_failed",
        "transaction.live_endpoint_scope_invalid",
        "transaction.live_env_missing",
        "transaction.live_json_number_invalid",
        "transaction.live_response_too_large",
    }
)
_SAFE_CODE = re.compile(r"transaction\.live_[a-z0-9_]+(?::([A-Za-z0-9_]+))?")


def _safe_probe_failure_code(error: Exception) -> str:
    message = str(error)
    match = _SAFE_CODE.fullmatch(message)
    if match is not None:
        base = message.split(":", 1)[0]
        suffix = match.group(1)
        if base in _SAFE_CODES:
            if suffix is None:
                return base
            if base == "transaction.live_case_failed" and suffix in _SAFE_CASE_IDS:
                return message
            return base
    if isinstance(error, httpx.TimeoutException):
        return "transaction.live_probe_timeout"
    if isinstance(error, httpx.HTTPError):
        return "transaction.live_probe_http_error"
    if isinstance(error, ValueError):
        return "transaction.live_probe_value_error"
    if isinstance(error, RuntimeError):
        return "transaction.live_probe_runtime_error"
    if isinstance(error, TypeError):
        return "transaction.live_probe_exception_type_error"
    return "transaction.live_probe_unexpected_error"


def _safe_live_probe(test: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    @functools.wraps(test)
    async def wrapped(*args: object, **kwargs: object) -> None:
        try:
            await test(*args, **kwargs)
        except Exception as error:
            raise AssertionError(_safe_probe_failure_code(error)) from None

    return wrapped


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"transaction.live_env_missing:{name}")
    return value


class LiveTransactionTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.calls = 0
        self.relative_paths: list[str] = []
        self.json_number_only = True

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.calls += 1
        response = await self._request(request.request, authorization=request.authorization)
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=_content_type(response),
            body=response.content,
        )

    async def send_without_authorization(self, request: BusinessHttpRequest) -> httpx.Response:
        self.calls += 1
        return await self._request(request, authorization=None)

    async def _request(self, request: BusinessHttpRequest, *, authorization: str | None) -> httpx.Response:
        relative_path = request.relative_path
        json_body = request.json_body
        if relative_path != "/txn/search" or json_body is None:
            raise AssertionError("transaction.live_endpoint_scope_invalid")
        body = bytes(json_body.content)
        if re.search(rb'"amount(?:Gt|Lt)?"\s*:\s*"', body):
            self.json_number_only = False
            raise AssertionError("transaction.live_json_number_invalid")
        self.relative_paths.append(relative_path)
        headers = {"Accept-Encoding": "identity", "Content-Type": "application/json"}
        if authorization is not None:
            headers["Authorization"] = authorization
        response = await self._client.post(relative_path, headers=headers, content=body)
        if len(response.content) > 1_048_576:
            raise AssertionError("transaction.live_response_too_large")
        return response

    async def aclose(self) -> None:
        await self._client.aclose()


def _content_type(response: httpx.Response) -> str | None:
    raw = response.headers.get("Content-Type")
    return None if raw is None else raw.split(";", 1)[0].strip().lower()


def _context(token: str, case_id: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id=f"transaction-live-{case_id}",
        correlation_id=f"transaction-live-{case_id}",
        original_question="controlled local transaction search verification",
        subject_id="transaction-live-principal",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 10.0,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
@_safe_live_probe
async def test_actual_user_jwt_and_exact_amount_matrix_through_transaction_adapter() -> None:
    base_url = _required("TRANSACTION_LIVE_BASE_URL")
    probe_path = Path(_required("TRANSACTION_LIVE_PROBE_EVIDENCE_PATH"))
    sentinel = _required("TRANSACTION_LIVE_SENTINEL")
    definition = transaction_search_definition()
    settings = TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}).action
    client = httpx.AsyncClient(
        base_url=base_url,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(5.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    transport = LiveTransactionTransport(client)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="t" * 64,
        max_user_result_bytes=262_144,
    )
    matrix: dict[str, str] = {}
    try:
        for case_id, token_name, arguments in (
            ("adminPrimary", "TRANSACTION_LIVE_ADMIN_JWT", {"amount": "0.01"}),
            ("adminSecondary", "TRANSACTION_LIVE_DYLAN_JWT", {"amount_gt": "-9999999999999999.99"}),
            ("viewer", "TRANSACTION_LIVE_VIEWER_JWT", {"amount_lt": "9999999999999999.99"}),
        ):
            input_value = definition.argument_validator.validate(arguments)
            result = await handler.handle(input_value, _context(_required(token_name), case_id))
            if result.status is not CapabilityStatus.NO_RESULT or result.domain_result is not None:
                raise AssertionError(f"transaction.live_case_failed:{case_id}")
            if result.egress.disposition is not EgressDisposition.NOT_APPLICABLE:
                raise AssertionError(f"transaction.live_case_failed:{case_id}")
            matrix[case_id] = "allowed"

        denied_input = definition.argument_validator.validate({"trans_id": sentinel})
        for case_id, token_name, expected in (
            ("unknownRole", "TRANSACTION_LIVE_UNKNOWN_ROLE_JWT", CapabilityStatus.FORBIDDEN),
            ("malformedToken", "TRANSACTION_LIVE_MALFORMED_JWT", CapabilityStatus.UNAUTHENTICATED),
            ("serviceToken", "TRANSACTION_LIVE_SERVICE_JWT", CapabilityStatus.UNAUTHENTICATED),
        ):
            result = await handler.handle(denied_input, _context(_required(token_name), case_id))
            if result.status is not expected or result.domain_result is not None:
                raise AssertionError(f"transaction.live_case_failed:{case_id}")
            matrix[case_id] = "forbidden" if expected is CapabilityStatus.FORBIDDEN else "unauthenticated"

        wire = definition.request_mapper.map(denied_input, settings)
        missing = await transport.send_without_authorization(definition.wire_codec.encode(wire))
        if not isinstance(missing, httpx.Response) or missing.status_code != 401:
            raise AssertionError("transaction.live_case_failed:missingToken")
        matrix["missingToken"] = "unauthenticated"
        if len(transport.relative_paths) != 7 or set(transport.relative_paths) != {"/txn/search"}:
            raise AssertionError("transaction.live_endpoint_scope_invalid")
        probe = {
            "schemaVersion": 1,
            "authorizationMatrix": matrix,
            "precisionMatrix": {"jsonNumberOnly": transport.json_number_only},
            "requestCounts": {
                "transaction": transport.calls,
                "adapter": transport.calls - 1,
                "otherTransactionEndpoints": 0,
                "model": 0,
            },
            "responseVisibility": "empty_response_with_provider_contract",
        }
        validate_probe_evidence(probe)
        probe_path.write_text(json.dumps(probe, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    finally:
        await transport.aclose()
