from __future__ import annotations

import json
from dataclasses import asdict

import httpx
import pytest

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.main import build_runtime
from agent_runtime.model.deepseek import transport as transport_module
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import (
    _FixedStream,
    _KnowledgeClientFactory,
    _enabled_environment,
)


_QUESTION = "2016年生活服务增值税政策"
_SYNTHETIC_KEY = "nonlive-provider-boundary-key"
_RESPONSE_MARKER = "synthetic-response-must-not-be-observed"


def _envelope(content, *, finish_reason="stop"):
    return {
        "object": "chat.completion",
        "model": ModelSettings.MODEL_NAME,
        "choices": [{
            "index": 0,
            "finish_reason": finish_reason,
            "message": {"content": content},
        }],
        "usage": {"total_tokens": 0},
    }


@pytest.mark.parametrize("fault, expected, model_failure, provider_decoded", [
    ("none", CapabilityStatus.SUCCESS, None, True),
    ("clarification", CapabilityStatus.NO_RESULT, None, True),
    ("content_type", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False),
    ("outer_json", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False),
    ("provider_model", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False),
    ("finish_length", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False),
    ("task_json", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True),
    ("task_duplicate_key", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True),
    ("task_extra_field", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True),
    ("task_unknown_condition", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True),
    ("semantic_date", CapabilityStatus.DOWNSTREAM_FAILURE, None, True),
    ("http_error", CapabilityStatus.DOWNSTREAM_FAILURE, "provider_failure", False),
    ("timeout", CapabilityStatus.TIMEOUT, "provider_timeout", False),
])
@pytest.mark.asyncio
async def test_wire_response_to_current_rewrite_runtime_fails_closed(
    monkeypatch, caplog, fault, expected, model_failure, provider_decoded,
):
    """Synthetic wire faults test boundary semantics, not live model correctness."""
    calls = []
    # Current production binding; frozen run tests inject their original root.
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    expected_rewrite = tasks.rewrite.build_request(KnowledgeSemanticPlanInput(
        minimized_question=_QUESTION, enabled_domain_ids=("tax.policy", "tax.law")))
    decoded_calls = []
    business_calls = 0
    parse_response = transport_module.parse_deepseek_response

    async def reject_business(self, outbound):
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("Knowledge must never call Business")

    monkeypatch.setattr(HttpxBusinessDomainTransport, "send", reject_business)

    def observe_decode(raw, *, max_bytes):
        # Observe successful provider decoding without replacing either decoder.
        result = parse_response(raw, max_bytes=max_bytes)
        decoded_calls.append(len(calls))
        return result

    monkeypatch.setattr(transport_module, "parse_deepseek_response", observe_decode)

    async def respond(request):
        assert request.method == "POST"
        assert str(request.url) == ModelSettings.BASE_URL + "/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + _SYNTHETIC_KEY
        payload = json.loads(request.content)
        calls.append(payload)
        user_input = json.loads(payload["messages"][1]["content"])
        content_type = "application/json"
        if len(calls) == 1:
            content = '{"capability_id":"knowledge.query"}'
        elif len(calls) == 2:
            assert payload["messages"][0]["content"] == expected_rewrite.system_instruction
            assert payload["max_tokens"] == 512
            assert payload["response_format"] == {"type": "json_object"}
            assert "tools" not in payload
            assert user_input["question"] == _QUESTION
            value = {
                "outcome": "search",
                "queries": [{"domain_id": "tax.policy", "query": _QUESTION}],
                "missing_conditions": [],
            }
            if fault in {"clarification", "task_unknown_condition"}:
                value.update(outcome="clarification_required", queries=[],
                             missing_conditions=["taxpayer_type" if fault == "clarification" else "invented"])
            elif fault == "semantic_date":
                value["queries"][0]["query"] = _QUESTION.replace("2016", "2026")
            elif fault == "task_extra_field":
                value["extra"] = _RESPONSE_MARKER
            content = json.dumps(value, ensure_ascii=False)
            if fault == "task_json":
                content = _RESPONSE_MARKER
            elif fault == "task_duplicate_key":
                content = '{"outcome":"search",' + content[1:]
            elif fault == "http_error":
                return httpx.Response(503, stream=_FixedStream(_RESPONSE_MARKER.encode()))
            elif fault == "timeout":
                raise httpx.ReadTimeout("synthetic", request=request)
        else:
            assert len(calls) == 3 and fault == "none"
            first = user_input["evidence"][0]
            content = json.dumps({"outcome": "answer", "points": [{
                "evidence_ref": first["evidence_ref"], "quote": first["content"],
            }]}, ensure_ascii=False)
        envelope = _envelope(content)
        if len(calls) == 2:
            if fault == "content_type":
                content_type = "text/plain"
            elif fault == "provider_model":
                envelope["model"] = "unexpected-model"
            elif fault == "finish_length":
                envelope["choices"][0]["finish_reason"] = "length"
        raw = json.dumps(envelope, ensure_ascii=False).encode()
        if len(calls) == 2 and fault == "outer_json":
            raw = _RESPONSE_MARKER.encode()
        return httpx.Response(200, headers={"Content-Type": content_type}, stream=_FixedStream(raw))

    # All HTTP is intercepted. No process environment or real credential is read.
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(_SYNTHETIC_KEY))
    clients = _KnowledgeClientFactory()
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, trust_env=False,
                                transport=httpx.MockTransport(respond)) as client:
        runtime = build_runtime(
            _enabled_environment(),
            model_transport=transport_module.DeepSeekChatTransport(settings=settings, client=client),
            knowledge_http_client_factory=clients,
        )
        try:
            with observation_scope() as collector:
                outcome = await runtime.ainvoke(question=_QUESTION, scope=scope(_QUESTION))
                observations = collector.snapshot()
        finally:
            await runtime.aclose()

    assert outcome.status is expected, outcome.failure
    assert outcome.capability_id == "knowledge.query"
    assert business_calls == 0
    assert (2 in decoded_calls) is provider_decoded
    assert len(calls) == (3 if fault == "none" else 2)
    assert [(row["taskId"], row["taskVersion"]) for row in observations.model_calls] == [
        ("action_selection", "action-selection-v4"), ("knowledge_rewrite", expected_rewrite.task_version),
    ] + ([("knowledge_summary", "4")] if fault == "none" else [])
    rewrite = observations.model_calls[1]
    assert rewrite["status"] == ("failed" if model_failure else "succeeded")
    assert rewrite["failureKind"] == model_failure
    if fault == "none":
        assert clients.paths.count("/es/knowledge/search") == 2
        assert clients.paths.count("/embed") == clients.paths.count("/rerank") == 1
    else:
        assert clients.paths == []
        assert observations.downstream_calls == ()
        assert observations.plans == ()
    if fault == "clarification":
        assert outcome.user_result["reason"] == "clarification_required"
    visible = json.dumps(asdict(observations), ensure_ascii=False) + str(outcome) + caplog.text
    for forbidden in (_SYNTHETIC_KEY, _RESPONSE_MARKER, "header.payload.signature"):
        assert forbidden not in visible
    assert client.is_closed and all(item.is_closed for item in clients.clients)
