from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

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
    OpaqueUserToken,
    SubjectType,
)
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.egress_input_qualification import (
    QualificationSelectionMode,
    build_qualification_probe,
    write_exclusive_json,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY") != "1",
    reason="requires explicit WP-EMP-EGRESS-INPUT-QUALIFY-01 opt-in",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.egress_input_qualify_env_missing:{name}")
    return value.strip()


def _base_url() -> str:
    value = _required("EMPLOYEE_EGRESS_QUALIFY_BASE_URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RuntimeError("employee.egress_input_qualify_endpoint_invalid")
    return value.rstrip("/")


class QualificationEmployeeTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.calls += 1
        if self.calls != 1 or request.request.method != "GET":
            raise RuntimeError("employee.egress_input_qualify_request_count_invalid")
        response = await self._client.get(
            request.request.relative_path,
            headers={
                "Authorization": request.authorization,
                "Accept-Encoding": "identity",
            },
        )
        content_type = response.headers.get("content-type")
        if content_type is not None:
            content_type = content_type.split(";", 1)[0].strip().lower()
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=content_type,
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="employee-egress-input-qualification",
        correlation_id="employee-egress-input-qualification",
        original_question="查询该员工的职位和工作地",
        subject_id="employee-egress-input-qualification-reader",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
async def test_single_real_employee_detail_qualifies_input_without_model(
    capfd: pytest.CaptureFixture[str],
) -> None:
    if "LLM_API_KEY" in os.environ:
        raise RuntimeError("employee.egress_input_qualify_model_key_visible")
    identifier = _required("EMPLOYEE_EGRESS_QUALIFY_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_QUALIFY_ADMIN_JWT")
    selection_mode = QualificationSelectionMode(
        _required("EMPLOYEE_EGRESS_QUALIFY_SELECTION_MODE")
    )
    database_selection_rows = int(_required("EMPLOYEE_EGRESS_QUALIFY_DATABASE_ROWS"))
    output_path = Path(_required("EMPLOYEE_EGRESS_QUALIFY_PROBE_OUTPUT"))

    definition = employee_detail_definition()
    settings = EmployeeAdapterSettings.from_env(
        {
            "AGENT_EMPLOYEE_DETAIL_ENABLED": "true",
            "AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": "position,work_base_si",
        }
    ).action
    client = httpx.AsyncClient(
        base_url=_base_url(),
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(8.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    transport = QualificationEmployeeTransport(client)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(
            transport=transport,
            max_response_bytes=1_048_576,
        ),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(
            BusinessGlobalSettings(egress_enabled=True)
        ),
        config_snapshot_id=hashlib.sha256(
            b"employee-egress-input-qualification-v1"
        ).hexdigest(),
        max_user_result_bytes=262_144,
    )

    try:
        result = await handler.handle(
            definition.argument_validator.validate({"employee_identifier": identifier}),
            _context(token),
        )
        sensitive_literals = {identifier, token}
        if isinstance(result.domain_result, Mapping):
            records = result.domain_result.get("records")
            if isinstance(records, tuple):
                for record in records:
                    if not isinstance(record, Mapping):
                        continue
                    fields = record.get("fields")
                    if not isinstance(fields, Mapping):
                        continue
                    sensitive_literals.update(
                        value
                        for value in fields.values()
                        if isinstance(value, str) and value
                    )
        probe = build_qualification_probe(
            selection_mode=selection_mode,
            result=result,
            database_selection_rows=database_selection_rows,
            employee_detail_requests=transport.calls,
        )
        captured = capfd.readouterr()
        captured_text = captured.out + captured.err
        if any(value in captured_text for value in sensitive_literals):
            raise RuntimeError("employee.egress_input_qualify_log_leak")
        write_exclusive_json(output_path, probe)
    finally:
        await client.aclose()
