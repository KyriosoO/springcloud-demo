from __future__ import annotations

import json

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityStatus, EgressDisposition
from tests.helpers import scope


class FakeEmployeeServer:
    def __init__(self) -> None:
        self.requests: list[FakeDomainHttpRequest] = []

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.requests.append(request)
        body = {
            "idCardNo": "ABCDE", "memberNo": "MEM01", "chineseName": "测试员工",
            "publicEmail": "test@example.invalid", "position": "工程师", "workBaseSi": "上海",
            "rawSensitiveField": "not-projected",
        }
        return FakeDomainHttpResponse(status_code=200, content_type="application/json", body=json.dumps(body, ensure_ascii=False).encode())

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_employee_handler_calls_fake_once_and_returns_six_field_projection_with_default_zero_egress() -> None:
    definition = employee_detail_definition()
    settings = EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}).action
    server = FakeEmployeeServer()
    handler = BoundBusinessActionHandler(
        definition=definition, settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1048576),
        user_projector=BusinessUserResultProjector(), egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="a" * 64, max_user_result_bytes=262144,
    )
    input = definition.argument_validator.validate({"employee_identifier": "ABCDE"})
    result = await handler.handle(input, scope("查询员工详情").context)

    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.DENIED
    assert len(server.requests) == 1
    assert server.requests[0].authorization.startswith("Bearer ")
    record = result.domain_result["records"][0]  # type: ignore[index]
    assert record["fields"]["employee_id_masked"] == "***BCDE"  # type: ignore[index]
    assert "rawSensitiveField" not in str(result.domain_result)

