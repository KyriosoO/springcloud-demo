from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from agent_runtime.adapters.employee.definition import (
    employee_search_definition,
    employee_semantic_search_definition,
)
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    UserJwtBusinessHttpClient,
)
from agent_runtime.business.settings import (
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    GlobalBusinessEgressPolicy,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityStatus, EgressDisposition
from tests.helpers import scope


class FakeEmployeeSearchServer:
    def __init__(self, *, status: int = 200) -> None:
        self.requests: list[FakeDomainHttpRequest] = []
        self.status = status

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.requests.append(request)
        body = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_source": {
                    "idCardNo": "ABCDE12345",
                    "chineseName": "测试员工",
                    "contactAddress": "上海市测试路",
                    "position": "工程师",
                    "workBaseSi": "not-user-visible",
                    "privateData": "not-user-visible",
                }}],
            },
        }
        return FakeDomainHttpResponse(
            status_code=self.status,
            content_type="text/plain;charset=UTF-8",
            body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_search_handler_uses_one_endpoint_jwt_and_masked_list_without_answer_call() -> None:
    definition = employee_search_definition()
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)["employee.search"]
    server = FakeEmployeeSearchServer()
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1048576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="a" * 64,
        max_user_result_bytes=262144,
    )
    selected = definition.argument_validator.validate({
        "filters": ({"field": "contact_address", "operator": "contains", "value": "上海"},),
        "page": 1,
        "size": 20,
        "sorts": (),
    })
    result = await handler.handle(selected, scope("帮我查一下在上海的员工").context)

    assert len(server.requests) == 1
    assert server.requests[0].request.relative_path == "/employees/es/search"
    assert server.requests[0].authorization.startswith("Bearer ")
    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.NOT_APPLICABLE
    assert result.domain_result is not None
    records = result.domain_result["records"]
    assert isinstance(records, tuple)
    assert isinstance(records[0], Mapping)
    fields = records[0]["fields"]
    assert isinstance(fields, Mapping)
    assert fields["employee_identifier"] == "***2345"
    assert fields["chinese_name"] == "测***"
    assert fields["contact_address"] == "上海***"
    assert fields["position"] == "工程师"
    assert "work_base_si" not in fields
    assert "privateData" not in str(result.domain_result)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", ((401, CapabilityStatus.UNAUTHENTICATED), (403, CapabilityStatus.FORBIDDEN)))
async def test_search_handler_preserves_service_final_authorization(
    status: int,
    expected: CapabilityStatus,
) -> None:
    definition = employee_search_definition()
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)["employee.search"]
    server = FakeEmployeeSearchServer(status=status)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1048576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="a" * 64,
        max_user_result_bytes=262144,
    )
    selected = definition.argument_validator.validate({
        "filters": ({"field": "contact_address", "operator": "contains", "value": "上海"},),
        "page": 1,
        "size": 20,
        "sorts": (),
    })
    result = await handler.handle(selected, scope("查上海员工").context)
    assert result.status is expected
    assert result.domain_result is None
    assert len(server.requests) == 1


@pytest.mark.asyncio
async def test_semantic_handler_uses_only_vector_endpoint_once() -> None:
    definition = employee_semantic_search_definition()
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    server = FakeEmployeeSearchServer()
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1048576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="a" * 64,
        max_user_result_bytes=262144,
    )
    selected = definition.argument_validator.validate(
        {"query": "熟悉分布式系统的开发工程师", "size": 10}
    )
    result = await handler.handle(selected, scope("查擅长分布式系统的员工").context)
    assert len(server.requests) == 1
    assert server.requests[0].request.relative_path == "/employees/es/vector-search"
    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.NOT_APPLICABLE
