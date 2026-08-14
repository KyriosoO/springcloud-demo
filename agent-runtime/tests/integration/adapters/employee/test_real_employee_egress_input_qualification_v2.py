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
    CapabilityStatus,
    EgressDisposition,
    OpaqueUserToken,
    SubjectType,
)
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.egress_input_qualification_v2 import (
    QualificationFailurePhase,
    QualificationLifecycleJournalV2,
    QualificationReason,
    QualificationRunStatus,
    build_result,
    validate_lifecycle,
    write_exclusive_json,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2") != "1",
    reason="requires a separately authorized GATE-049 live execution",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.egress_input_qualification_v2_env_missing:{name}")
    return value.strip()


def _base_url() -> str:
    value = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_BASE_URL")
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
        raise RuntimeError("employee.egress_input_qualification_v2_endpoint_invalid")
    return value.rstrip("/")


class QualificationEmployeeTransportV2:
    def __init__(
        self,
        client: httpx.AsyncClient,
        journal: QualificationLifecycleJournalV2,
    ) -> None:
        self._client = client
        self._journal = journal
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls != 0 or request.request.method != "GET":
            raise RuntimeError("employee.egress_input_qualification_v2_request_count_invalid")
        self._journal.record_employee_detail_started()
        self.calls = 1
        try:
            response = await self._client.get(
                request.request.relative_path,
                headers={
                    "Authorization": request.authorization,
                    "Accept-Encoding": "identity",
                },
            )
        except BaseException:
            self._journal.record_employee_detail_terminal(status="failed")
            raise
        self._journal.record_employee_detail_terminal(status="completed")
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
        request_id="employee-egress-input-qualification-v2",
        correlation_id="employee-egress-input-qualification-v2",
        original_question="查询该员工的职位和工作地",
        subject_id="employee-egress-input-qualification-v2-reader",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
async def test_single_real_employee_detail_produces_finite_qualification_result_v2(
    capfd: pytest.CaptureFixture[str],
) -> None:
    if "LLM_API_KEY" in os.environ:
        raise RuntimeError("employee.egress_input_qualification_v2_model_key_visible")
    identifier = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_ADMIN_JWT")
    manifest_sha = _required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_MANIFEST_SHA256")
    lifecycle_path = Path(_required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_LIFECYCLE"))
    result_path = Path(_required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_RESULT"))
    journal = QualificationLifecycleJournalV2.open_existing(
        lifecycle_path,
        manifest_sha256=manifest_sha,
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
    transport = QualificationEmployeeTransportV2(client, journal)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(
            BusinessGlobalSettings(egress_enabled=True)
        ),
        config_snapshot_id=hashlib.sha256(b"employee-egress-input-qualification-v2").hexdigest(),
        max_user_result_bytes=262_144,
    )

    result = None
    try:
        result = await handler.handle(
            definition.argument_validator.validate({"employee_identifier": identifier}),
            _context(token),
        )
        if result.status is not CapabilityStatus.SUCCESS:
            journal.record_run_terminal(
                status=QualificationRunStatus.FAILED,
                failure_phase=QualificationFailurePhase.EMPLOYEE_DETAIL,
                failure_reason=QualificationReason.EMPLOYEE_REQUEST_FAILED,
            )
        else:
            fields: Mapping[str, object] = {}
            if isinstance(result.domain_result, Mapping):
                records = result.domain_result.get("records")
                if isinstance(records, tuple) and len(records) == 1 and isinstance(records[0], Mapping):
                    candidate_fields = records[0].get("fields")
                    if isinstance(candidate_fields, Mapping):
                        fields = candidate_fields
            minimums = tuple(
                isinstance(fields.get(field), str) and bool(str(fields[field]).strip())
                for field in ("employee_id_masked", "chinese_name", "position", "work_base_si")
            )
            if not all(minimums):
                journal.record_run_terminal(
                    status=QualificationRunStatus.NOT_QUALIFIED,
                    failure_phase=QualificationFailurePhase.EMPLOYEE_RESULT,
                    failure_reason=QualificationReason.EMPLOYEE_RESULT_INVALID,
                )
            elif (
                result.egress.disposition is not EgressDisposition.ALLOWED
                or result.egress.safe_payload is None
            ):
                journal.record_run_terminal(
                    status=QualificationRunStatus.NOT_QUALIFIED,
                    failure_phase=QualificationFailurePhase.EGRESS_PROJECTION,
                    failure_reason=QualificationReason.EGRESS_PROJECTION_INVALID,
                )
            else:
                journal.record_run_terminal(
                    status=QualificationRunStatus.QUALIFIED,
                    failure_phase=None,
                    failure_reason=None,
                )
        captured = capfd.readouterr()
        if identifier in captured.out + captured.err or token in captured.out + captured.err:
            raise RuntimeError("employee.egress_input_qualification_v2_log_leak")
        write_exclusive_json(
            result_path,
            build_result(
                lifecycle_path=lifecycle_path,
                manifest_sha256=manifest_sha,
                result=result,
                raw_logs_deleted=False,
                log_leak_count=0,
            ),
        )
    except BaseException:
        snapshot = validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha)
        if snapshot.run_status is None:
            if snapshot.employee_detail_started == 1 and snapshot.employee_detail_terminal == 0:
                journal.record_employee_detail_terminal(status="failed")
            journal.record_run_terminal(
                status=QualificationRunStatus.FAILED,
                failure_phase=QualificationFailurePhase.EMPLOYEE_DETAIL,
                failure_reason=QualificationReason.EMPLOYEE_REQUEST_FAILED,
            )
        if not result_path.exists():
            write_exclusive_json(
                result_path,
                build_result(
                    lifecycle_path=lifecycle_path,
                    manifest_sha256=manifest_sha,
                    result=result,
                    raw_logs_deleted=False,
                    log_leak_count=0,
                ),
            )
        raise
    finally:
        await client.aclose()
