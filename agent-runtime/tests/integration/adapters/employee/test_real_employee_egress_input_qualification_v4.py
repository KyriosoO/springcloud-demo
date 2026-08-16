from __future__ import annotations

import asyncio
import hashlib
import json
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
    CapabilityStatus,
    EgressDisposition,
    OpaqueUserToken,
    SubjectType,
)
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.egress_input_qualification_v4 import (
    LifecycleJournal,
    QualificationOutcome,
    write_exclusive_json,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V4") != "1",
    reason="requires a separately authorized GATE-049 candidate-04 execution",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.qualification_v4_env_missing:{name}")
    return value.strip()


def _base_url() -> str:
    value = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_BASE_URL")
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
        raise RuntimeError("employee.qualification_v4_endpoint_invalid")
    return value.rstrip("/")


class QualificationTransportV4:
    def __init__(self, client: httpx.AsyncClient, journal: LifecycleJournal) -> None:
        self.client = client
        self.journal = journal
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls != 0 or request.request.method != "GET":
            raise RuntimeError("employee.qualification_v4_request_count_invalid")
        self.journal.record(phase="employee_detail", state="started")
        self.calls = 1
        try:
            response = await self.client.get(
                request.request.relative_path,
                headers={"Authorization": request.authorization, "Accept-Encoding": "identity"},
            )
        except BaseException:
            self.journal.record(
                phase="employee_detail", state="failed", reason="employee_request_failed"
            )
            raise
        self.journal.record(phase="employee_detail", state="succeeded")
        content_type = response.headers.get("content-type")
        if content_type is not None:
            content_type = content_type.split(";", 1)[0].strip().lower()
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=content_type,
            body=response.content,
        )

    async def aclose(self) -> None:
        await self.client.aclose()


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="employee-qualification-v4",
        correlation_id="employee-qualification-v4",
        original_question="查询该员工的职位和工作地",
        subject_id="employee-qualification-v4-reader",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
async def test_single_synthetic_employee_detail_writes_only_finite_staging(
    capfd: pytest.CaptureFixture[str],
) -> None:
    if "LLM_API_KEY" in os.environ:
        raise RuntimeError("employee.qualification_v4_model_key_visible")
    identifier = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_ADMIN_JWT")
    manifest_sha = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_MANIFEST_SHA256")
    lifecycle_path = Path(_required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_LIFECYCLE"))
    staging_path = Path(_required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V4_STAGING"))
    journal = LifecycleJournal.open_existing(
        lifecycle_path, manifest_sha256=manifest_sha
    )

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
    transport = QualificationTransportV4(client, journal)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(
            BusinessGlobalSettings(egress_enabled=True)
        ),
        config_snapshot_id=hashlib.sha256(b"employee-qualification-v4").hexdigest(),
        max_user_result_bytes=262_144,
    )
    try:
        result = await handler.handle(
            definition.argument_validator.validate({"employee_identifier": identifier}),
            _context(token),
        )
        fields: Mapping[str, object] = {}
        if isinstance(result.domain_result, Mapping):
            records = result.domain_result.get("records")
            if isinstance(records, tuple) and len(records) == 1 and isinstance(records[0], Mapping):
                candidate = records[0].get("fields")
                if isinstance(candidate, Mapping):
                    fields = candidate
        codec = {
            "idCardNo": _present(fields.get("employee_id_masked")),
            "chineseName": _present(fields.get("chinese_name")),
            "position": _present(fields.get("position")),
            "workBaseSi": _present(fields.get("work_base_si")),
        }
        outcome = QualificationOutcome(
            codec_fields=codec,
            required_user_fields={
                "employeeIdMasked": codec["idCardNo"],
                "chineseName": codec["chineseName"],
            },
            egress_allowed=(
                result.status is CapabilityStatus.SUCCESS
                and result.egress.disposition is EgressDisposition.ALLOWED
                and result.egress.safe_payload is not None
            ),
        )
        captured = capfd.readouterr()
        if identifier in captured.out + captured.err or token in captured.out + captured.err:
            raise RuntimeError("employee.qualification_v4_log_leak")
        write_exclusive_json(
            staging_path,
            {
                "schemaVersion": 4,
                "codec": dict(outcome.codec_fields),
                "requiredUser": dict(outcome.required_user_fields),
                "egressAllowed": outcome.egress_allowed,
                "requestSucceeded": result.status is CapabilityStatus.SUCCESS,
            },
        )
    finally:
        await client.aclose()


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
