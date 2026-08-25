from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from agent_runtime.adapters.transaction.definition import transaction_list_search_definition
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


class FakeTransactionListServer:
    def __init__(self, *, status: int = 200) -> None:
        self.requests: list[FakeDomainHttpRequest] = []
        self.status = status

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.requests.append(request)
        response = {
            "rows": [{
                "transId": "TXN-00000001",
                "transType": "PAYMENT",
                "transDate": 1787619600000,
                "amount": 100.25,
                "transDateGt": None,
                "transDateLt": None,
                "amountGt": None,
                "amountLt": None,
                "transTypeContains": None,
            }],
            "total": 1,
            "totalExact": True,
            "page": 1,
            "size": 20,
        }
        return FakeDomainHttpResponse(
            status_code=self.status,
            content_type="application/json",
            body=json.dumps(response).encode("utf-8"),
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_transaction_list_handler_uses_one_fixed_endpoint_and_masked_results() -> None:
    definition = transaction_list_search_definition()
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "transaction.search"
    ]
    server = FakeTransactionListServer()
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
        "filters": ({"field": "trans_type", "operator": "contains", "value": "PAY"},),
        "page": 1,
        "size": 20,
        "sorts": (),
    })

    result = await handler.handle(selected, scope("查询交易类型包含 PAY 的交易").context)

    assert len(server.requests) == 1
    assert server.requests[0].request.relative_path == "/txn/search"
    assert server.requests[0].authorization.startswith("Bearer ")
    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.NOT_APPLICABLE
    assert result.domain_result is not None
    records = result.domain_result["records"]
    assert isinstance(records, tuple)
    assert isinstance(records[0], Mapping)
    fields = records[0]["fields"]
    assert isinstance(fields, Mapping)
    assert fields == {
        "trans_id": "***0001",
        "trans_type": "PAYMENT",
        "trans_date": "2026-08-25T09:00:00+08:00",
        "amount": "100.25",
    }
    assert "TXN-00000001" not in str(result.domain_result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected", ((401, CapabilityStatus.UNAUTHENTICATED), (403, CapabilityStatus.FORBIDDEN))
)
async def test_transaction_list_handler_keeps_service_final_authorization(
    status: int, expected: CapabilityStatus
) -> None:
    definition = transaction_list_search_definition()
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "transaction.search"
    ]
    server = FakeTransactionListServer(status=status)
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
        "filters": ({"field": "trans_type", "operator": "eq", "value": "PAY"},),
        "page": 1,
        "size": 20,
        "sorts": (),
    })

    result = await handler.handle(selected, scope("查询支付交易").context)

    assert result.status is expected
    assert len(server.requests) == 1
