from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_runtime.api.models import RuntimeInvokeRequest, RuntimeInvokeResponse
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.capability_api.contracts import CapabilityStatus
from tests.api_helpers import runtime_request


def test_request_is_strict_and_preserves_the_single_question_value() -> None:
    request = RuntimeInvokeRequest.model_validate(runtime_request(question="  税务政策  "))

    assert request.question == "  税务政策  "
    assert request.model_dump(by_alias=True)["question"] == "  税务政策  "


@pytest.mark.parametrize(
    "change",
    (
        {"unexpected": True},
        {"contractVersion": "1"},
        {"remainingTimeoutMs": 120001},
        {"question": " "},
        {"requestId": "\n"},
    ),
)
def test_request_rejects_contract_drift(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RuntimeInvokeRequest.model_validate(runtime_request(**change))


def test_response_rejects_success_with_failure() -> None:
    with pytest.raises(ValidationError):
        RuntimeInvokeResponse.model_validate(
            {
                "contractVersion": 1,
                "requestId": "req-1",
                "status": "success",
                "capabilityId": None,
                "answerText": "done",
                "userResult": None,
                "failure": {"code": "core.invalid_result", "source": "core"},
            }
        )


def test_settings_are_frozen_to_loopback_and_protocol_v1() -> None:
    settings = RuntimeHttpSettings.from_env({})

    assert settings.host == "127.0.0.1"
    assert settings.contract_version == 1
    with pytest.raises(ValueError, match="AGENT_RUNTIME_HOST"):
        RuntimeHttpSettings(host="0.0.0.0")
    with pytest.raises(ValueError, match="AGENT_RUNTIME_CONTRACT_VERSION"):
        RuntimeHttpSettings(contract_version=2)
    with pytest.raises(ValueError, match="AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES"):
        RuntimeHttpSettings(max_incomplete_event_bytes=65536)
