from __future__ import annotations

import json

import pytest

from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelProviderFailureKind,
    ModelTaskId,
    StructuredModelRequest,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.dto import parse_deepseek_response, project_deepseek_request
from agent_runtime.model.deepseek.errors import (
    DeepSeekTransportFailure,
    DeepSeekTransportFailureCategory,
    DeepSeekTransportPhase,
    map_deepseek_failure,
)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.TIMEOUT, phase=DeepSeekTransportPhase.READ),
            ModelProviderFailureKind.PROVIDER_TIMEOUT,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.HTTP, status_code=408),
            ModelProviderFailureKind.PROVIDER_TIMEOUT,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.HTTP, status_code=504),
            ModelProviderFailureKind.PROVIDER_TIMEOUT,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.HTTP, status_code=429),
            ModelProviderFailureKind.PROVIDER_FAILURE,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.TRANSPORT),
            ModelProviderFailureKind.PROVIDER_FAILURE,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.PARSE),
            ModelProviderFailureKind.INVALID_OUTPUT,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.MODEL),
            ModelProviderFailureKind.INVALID_OUTPUT,
        ),
        (
            DeepSeekTransportFailure(category=DeepSeekTransportFailureCategory.SIZE),
            ModelProviderFailureKind.INVALID_OUTPUT,
        ),
    ],
)
def test_maps_every_private_failure_to_finite_neutral_kind(
    failure: DeepSeekTransportFailure,
    expected: ModelProviderFailureKind,
) -> None:
    assert map_deepseek_failure(failure) is expected
    assert not hasattr(failure, "body")
    assert not hasattr(failure, "message")


@pytest.mark.parametrize("status", [200, 201, 204, 301, 400, 401, 402, 403, 404, 422, 429, 500, 503])
def test_all_non_timeout_http_statuses_map_to_provider_failure(status: int) -> None:
    failure = DeepSeekTransportFailure(
        category=DeepSeekTransportFailureCategory.HTTP,
        status_code=status,
    )

    assert map_deepseek_failure(failure) is ModelProviderFailureKind.PROVIDER_FAILURE


def test_projects_exact_request_fields_without_caller_model_or_url() -> None:
    request = StructuredModelRequest(
        task_id=ModelTaskId.ANSWER_GENERATION,
        task_version="answer-v1",
        system_instruction="Return JSON.",
        user_payload_json='{"question":"税务政策"}',
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=128,
    )

    projected = project_deepseek_request(request).payload

    assert set(projected) == {
        "model",
        "messages",
        "thinking",
        "stream",
        "temperature",
        "max_tokens",
        "response_format",
    }
    assert projected["model"] == "deepseek-v4-pro"
    assert projected["stream"] is False
    assert projected["thinking"] == {"type": "disabled"}


def test_parses_valid_provider_response_and_ignores_safe_new_top_level() -> None:
    raw = json.dumps(
        {
            "id": "ignored",
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"content": '{"answer":"x"}'},
                }
            ],
            "usage": {"total_tokens": 12, "new_usage_field": 1},
            "new_top_level": "ignored",
        },
        separators=(",", ":"),
    ).encode()

    response = parse_deepseek_response(raw, max_bytes=4096)

    assert response.content == '{"answer":"x"}'
    assert response.usage_total_tokens == 12


@pytest.mark.parametrize(
    "raw",
    [
        b'{"object":"chat.completion","object":"duplicate"}',
        b'{"object":"chat.completion","model":"wrong","choices":[]}',
        b'{"object":"chat.completion","model":"deepseek-v4-pro","choices":[{"index":0,"finish_reason":"length","message":{"content":"x"}}]}',
        b'{"object":"chat.completion","model":"deepseek-v4-pro","choices":[{"index":0,"finish_reason":"stop","message":{"content":1}}]}',
        b'{"object":"chat.completion","model":"deepseek-v4-pro","choices":[{"index":0,"finish_reason":"stop","message":{"content":"\\ud800"}}]}',
    ],
)
def test_rejects_duplicate_or_invalid_consumed_provider_fields(raw: bytes) -> None:
    with pytest.raises(InvalidModelOutput):
        parse_deepseek_response(raw, max_bytes=4096)
