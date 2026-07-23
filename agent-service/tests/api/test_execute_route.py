from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agent_service.api.routes import router
from agent_service.api.schemas import AgentExecuteResponse


class FakeExecution:
    async def execute(self, request_id, received_at, request, bearer):
        assert bearer == "user-token"
        return AgentExecuteResponse(
            requestId=request_id,
            type="CLARIFICATION",
            data={"reasonCode": "TEST"},
        )


def _client() -> TestClient:
    app = FastAPI()
    app.state.agent_execution = FakeExecution()

    @app.middleware("http")
    async def context(request: Request, call_next):
        request.state.request_id = uuid4()
        request.state.received_at = datetime.now(UTC)
        return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def test_missing_bearer_is_401_with_server_request_id():
    response = _client().post("/api/agent/v1/execute", json={"message": "员工"})
    assert response.status_code == 401
    assert response.json()["requestId"]


def test_unknown_request_field_is_rejected_before_execution():
    response = _client().post(
        "/api/agent/v1/execute",
        headers={"Authorization": "Bearer user-token"},
        json={"message": "员工", "requestId": "caller-controlled"},
    )
    assert response.status_code == 422


def test_clarification_is_success():
    response = _client().post(
        "/api/agent/v1/execute",
        headers={"Authorization": "Bearer user-token"},
        json={"message": "员工"},
    )
    assert response.status_code == 200
    assert response.json()["type"] == "CLARIFICATION"
