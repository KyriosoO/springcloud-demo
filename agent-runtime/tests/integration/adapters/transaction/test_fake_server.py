from __future__ import annotations

import pytest

from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityStatus, EgressDisposition
from tests.helpers import scope


class FakeTransactionServer:
    def __init__(self) -> None:
        self.requests: list[FakeDomainHttpRequest] = []

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.requests.append(request)
        return FakeDomainHttpResponse(
            status_code=200, content_type="application/json",
            body=b'{"rows":[{"transId":"T0001","transType":"PAY","amount":100.0100}],"total":1,"totalExact":true,"page":1,"size":20}',
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_transaction_handler_calls_search_once_preserves_amount_and_defaults_model_egress_off() -> None:
    definition = transaction_search_definition()
    settings = TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}).action
    server = FakeTransactionServer()
    handler = BoundBusinessActionHandler(
        definition=definition, settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1048576),
        user_projector=BusinessUserResultProjector(), egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings()),
        config_snapshot_id="a" * 64, max_user_result_bytes=262144,
    )
    input = definition.argument_validator.validate({"amount_gt": "100.0100"})
    result = await handler.handle(input, scope("查询交易").context)

    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.DENIED
    assert len(server.requests) == 1
    request_body = server.requests[0].request.json_body
    assert request_body is not None and b'"amountGt":100.01' in request_body.content
    assert b'"100.01"' not in request_body.content
    record = result.domain_result["records"][0]  # type: ignore[index]
    assert record["fields"]["amount"] == "100.01"  # type: ignore[index]

