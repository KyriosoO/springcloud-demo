from __future__ import annotations

import asyncio
import functools
import json
import os
import re
from collections.abc import Mapping
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    UserJwtBusinessHttpClient,
)
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityStatus,
    EgressDisposition,
    JsonObject,
    OpaqueUserToken,
    SubjectType,
    canonical_json_bytes,
)
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.evidence_contract import validate_probe_evidence

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_LIVE") != "1",
    reason="requires explicit controlled Employee live opt-in",
)

_SAFE_CASE_IDS = frozenset(
    {"adminPrimary", "adminSecondary", "viewer", "unknownRole", "missingToken", "malformedToken", "serviceToken"}
)
_SAFE_LIVE_CODES = frozenset(
    {
        "employee.live_case_failed",
        "employee.live_endpoint_scope_invalid",
        "employee.live_env_missing",
        "employee.live_projection_failed",
        "employee.live_response_too_large",
        "employee.live_visibility_invalid",
    }
)
_SAFE_LIVE_CODE = re.compile(r"employee\.live_[a-z0-9_]+(?::([A-Za-z0-9_]+))?")


def _safe_probe_failure_code(error: Exception) -> str:
    message = str(error)
    match = _SAFE_LIVE_CODE.fullmatch(message)
    if match is not None:
        base_code = message.split(":", 1)[0]
        suffix = match.group(1)
        if base_code in _SAFE_LIVE_CODES:
            if suffix is None:
                return base_code
            if base_code in {"employee.live_case_failed", "employee.live_projection_failed"} and suffix in _SAFE_CASE_IDS:
                return message
            return base_code
    if isinstance(error, httpx.TimeoutException):
        return "employee.live_probe_timeout"
    if isinstance(error, httpx.HTTPError):
        return "employee.live_probe_http_error"
    if isinstance(error, ValueError):
        return "employee.live_probe_value_error"
    if isinstance(error, RuntimeError):
        return "employee.live_probe_runtime_error"
    if isinstance(error, TypeError):
        return "employee.live_probe_exception_type_error"
    return "employee.live_probe_unexpected_error"


def _safe_live_probe(
    test: Callable[..., Awaitable[None]],
) -> Callable[..., Awaitable[None]]:
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
        raise RuntimeError(f"employee.live_env_missing:{name}")
    return value


class LiveEmployeeTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.calls = 0
        self.relative_paths: list[str] = []
        self.visible_field_sets: list[frozenset[str]] = []

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.calls += 1
        response = await self._request(
            request.request.relative_path,
            authorization=request.authorization,
        )
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=_content_type(response),
            body=response.content,
        )

    async def send_without_authorization(self, relative_path: str) -> httpx.Response:
        self.calls += 1
        return await self._request(relative_path, authorization=None)

    async def _request(self, relative_path: str, *, authorization: str | None) -> httpx.Response:
        self.relative_paths.append(relative_path)
        headers = {"Accept-Encoding": "identity"}
        if authorization is not None:
            headers["Authorization"] = authorization
        response = await self._client.get(relative_path, headers=headers)
        if len(response.content) > 1_048_576:
            raise AssertionError("employee.live_response_too_large")
        if response.status_code == 200:
            payload = response.json()
            if type(payload) is not dict or any(type(key) is not str for key in payload):
                raise AssertionError("employee.live_visibility_invalid")
            self.visible_field_sets.append(frozenset(payload))
        return response

    async def aclose(self) -> None:
        await self._client.aclose()


def _content_type(response: httpx.Response) -> str | None:
    raw = response.headers.get("Content-Type")
    return None if raw is None else raw.split(";", 1)[0].strip().lower()


def _contains_identifier(domain_result: JsonObject, identifier: str) -> bool:
    return identifier.encode("utf-8") in canonical_json_bytes(domain_result)


def _context(token: str, case_id: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id=f"employee-live-{case_id}",
        correlation_id=f"employee-live-{case_id}",
        original_question="controlled local employee detail verification",
        subject_id="employee-live-principal",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 10.0,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
@_safe_live_probe
async def test_actual_user_jwt_matrix_through_employee_adapter() -> None:
    identifier = _required("EMPLOYEE_LIVE_TEST_IDENTIFIER")
    base_url = _required("EMPLOYEE_LIVE_BASE_URL")
    probe_path = Path(_required("EMPLOYEE_LIVE_PROBE_EVIDENCE_PATH"))
    visibility_fixture = (
        Path(_required("EMPLOYEE_LIVE_REPOSITORY_ROOT"))
        / "employee-service"
        / "src"
        / "test"
        / "resources"
        / "contracts"
        / "employee-detail-response-visibility-v1.json"
    )
    fixture = json.loads(visibility_fixture.read_text(encoding="utf-8"))
    expected_visible_fields = frozenset(fixture["fields"])
    if len(expected_visible_fields) != 58:
        raise AssertionError("employee.live_visibility_fixture_invalid")
    definition = employee_detail_definition()
    settings = EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}).action
    client = httpx.AsyncClient(
        base_url=base_url,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(5.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    transport = LiveEmployeeTransport(client)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="e" * 64,
        max_user_result_bytes=262_144,
    )
    input_value = definition.argument_validator.validate({"employee_identifier": identifier})
    matrix: dict[str, str] = {}
    try:
        for case_id, token_name in (
            ("adminPrimary", "EMPLOYEE_LIVE_ADMIN_JWT"),
            ("adminSecondary", "EMPLOYEE_LIVE_DYLAN_JWT"),
            ("viewer", "EMPLOYEE_LIVE_VIEWER_JWT"),
        ):
            result = await handler.handle(input_value, _context(_required(token_name), case_id))
            if result.status is not CapabilityStatus.SUCCESS or result.egress.disposition is not EgressDisposition.DENIED:
                raise AssertionError(f"employee.live_case_failed:{case_id}")
            if result.domain_result is None or _contains_identifier(result.domain_result, identifier):
                raise AssertionError(f"employee.live_projection_failed:{case_id}")
            records = result.domain_result.get("records")
            if type(records) is not tuple or len(records) != 1:
                raise AssertionError(f"employee.live_projection_failed:{case_id}")
            record = records[0]
            if not isinstance(record, Mapping):
                raise AssertionError(f"employee.live_projection_failed:{case_id}")
            fields = record.get("fields")
            if not isinstance(fields, Mapping) or not {"employee_id_masked", "chinese_name"}.issubset(fields):
                raise AssertionError(f"employee.live_projection_failed:{case_id}")
            matrix[case_id] = "allowed"

        for case_id, token_name, expected in (
            ("unknownRole", "EMPLOYEE_LIVE_UNKNOWN_ROLE_JWT", CapabilityStatus.FORBIDDEN),
            ("malformedToken", "EMPLOYEE_LIVE_MALFORMED_JWT", CapabilityStatus.UNAUTHENTICATED),
            ("serviceToken", "EMPLOYEE_LIVE_SERVICE_JWT", CapabilityStatus.UNAUTHENTICATED),
        ):
            result = await handler.handle(input_value, _context(_required(token_name), case_id))
            if result.status is not expected or result.domain_result is not None:
                raise AssertionError(f"employee.live_case_failed:{case_id}")
            matrix[case_id] = "forbidden" if expected is CapabilityStatus.FORBIDDEN else "unauthenticated"

        wire_request = definition.request_mapper.map(input_value, settings)
        request = definition.wire_codec.encode(wire_request)
        missing = await transport.send_without_authorization(request.relative_path)
        if missing.status_code != 401:
            raise AssertionError("employee.live_case_failed:missingToken")
        matrix["missingToken"] = "unauthenticated"
        if len(transport.visible_field_sets) != 3 or any(
            fields != expected_visible_fields for fields in transport.visible_field_sets
        ):
            raise AssertionError("employee.live_visibility_invalid")
        if len(transport.relative_paths) != 7 or set(transport.relative_paths) != {request.relative_path}:
            raise AssertionError("employee.live_endpoint_scope_invalid")
        probe = {
            "schemaVersion": 1,
            "authorizationMatrix": matrix,
            "requestCounts": {
                "employee": transport.calls,
                "adapter": transport.calls - 1,
                "otherEmployeeEndpoints": 0,
                "model": 0,
            },
            "responseVisibility": "validated_by_employee_adapter_and_fixture",
        }
        validate_probe_evidence(probe)
        probe_path.write_text(json.dumps(probe, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    finally:
        await transport.aclose()
