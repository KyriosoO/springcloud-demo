from __future__ import annotations

import asyncio
from dataclasses import replace
import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.intent_task_v12 import KnowledgeQueryIntentTaskV12
from agent_runtime.knowledge.evidence.summary_task_v9 import OUTPUT_NAME as SUMMARY_OUTPUT_NAME
from agent_runtime.knowledge.intent_task_v12 import OUTPUT_NAME as INTENT_OUTPUT_NAME
from agent_runtime.main import build_runtime
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelProviderFailureKind, ModelTaskId, ModelTransportError, StructuredFinishKind,
    StructuredModelRequest, StructuredModelResponse, StructuredToolCall,
)
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory, _enabled_environment


class MinimalModel:
    def __init__(self, intent: dict[str, object] | None = None) -> None:
        self.requests: list[StructuredModelRequest] = []
        self.intent = intent

    async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
        assert call_deadline > asyncio.get_running_loop().time()
        self.requests.append(request)
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP,
                content='{"capability_id":"knowledge.query"}', tool_calls=(), usage_total_tokens=0)
        payload = json.loads(request.user_payload_json)
        if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            assert request.task_version == "12"
            value = self.intent if self.intent is not None else {"outcome": "search", "query_mode": "lookup",
                "domains": {"tax.policy": "selected"}, "missing_conditions": []}
            name = INTENT_OUTPUT_NAME
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            assert request.task_version == "9" and payload["schema_version"] == 3
            first = payload["evidence"][0]
            mode = payload["query_mode"]
            claim = "" if mode == "lookup" else (
                "若题述事实准确，仅按指定条款，相关内容见引文。" if mode == "applicability"
                else "相关内容见引文。"
            )
            value = {"outcome": "answer", "points": [{"evidence_ref": first["evidence_ref"],
                "quote": first["content"], "claim": claim}]}
            name = SUMMARY_OUTPUT_NAME
        else:
            raise AssertionError("unrelated model task")
        return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
            tool_calls=(StructuredToolCall(name=name, arguments_json=json.dumps(value, ensure_ascii=False)),),
            usage_total_tokens=0)


@pytest.mark.asyncio
async def test_current_root_reaches_intent12_summary9_once_and_closes_owned_clients() -> None:
    model, clients = MinimalModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    question = "现行增值税政策有哪些"
    outcome = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()
    await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS, (outcome.failure, clients.paths)
    assert outcome.capability_id == "knowledge.query"
    assert [(item.task_id, item.task_version) for item in model.requests[1:]] == [
        (ModelTaskId.KNOWLEDGE_REWRITE, "12"), (ModelTaskId.KNOWLEDGE_SUMMARY, "9")]
    assert clients.paths.count("/embed") == 1
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/rerank") == 1
    assert len(clients.clients) == 3 and all(item.is_closed for item in clients.clients)


@pytest.mark.asyncio
async def test_knowledge_request_never_calls_employee_or_transaction_http(monkeypatch) -> None:
    class ForbiddenBusinessTransport:
        def __init__(self) -> None:
            self.calls = 0

        async def send(self, request: object) -> object:
            self.calls += 1
            raise AssertionError("Knowledge invoked Business domain HTTP")

        async def aclose(self) -> None:
            pass

    business_transports: list[ForbiddenBusinessTransport] = []

    def business_transport_factory(**kwargs: object) -> ForbiddenBusinessTransport:
        assert "base_endpoint" in kwargs and "allowed_paths" in kwargs
        transport = ForbiddenBusinessTransport()
        business_transports.append(transport)
        return transport

    monkeypatch.setattr("agent_runtime.main.HttpxBusinessDomainTransport", business_transport_factory)
    model, clients = MinimalModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "现行增值税政策有哪些"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS
    assert len(business_transports) == 2 and [item.calls for item in business_transports] == [0, 0]
    assert clients.paths.count("/es/knowledge/search") == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("intent,expected", [
    ({"outcome": "unsupported", "query_mode": "none", "domains": {"tax.policy": "not_selected"},
      "missing_conditions": []}, CapabilityStatus.NO_RESULT),
    ({"outcome": "search", "query_mode": "lookup", "domains": {"tax.policy": "selected"},
      "missing_conditions": [], "queries": []}, CapabilityStatus.DOWNSTREAM_FAILURE),
])
async def test_terminal_or_invalid_intent_has_zero_knowledge_downstream(
    intent: dict[str, object], expected: CapabilityStatus,
) -> None:
    model, clients = MinimalModel(intent), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "现行增值税政策有哪些"
    outcome = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()
    assert outcome.status is expected
    assert [(item.task_id, item.task_version) for item in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"), (ModelTaskId.KNOWLEDGE_REWRITE, "12")]
    assert not clients.paths
    if expected is CapabilityStatus.NO_RESULT:
        assert outcome.user_result == {"reason": "no_matching_domain",
                                       "selected_domain_ids": (), "coverage_complete": True}


@pytest.mark.asyncio
async def test_sensitive_question_overrides_hypothetical_zero_domain_intent() -> None:
    model = MinimalModel({"outcome": "unsupported", "query_mode": "none",
        "domains": {"tax.policy": "not_selected"}, "missing_conditions": []})
    clients = _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "税务政策 password=synthetic-secret"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.MODEL_EGRESS_DENIED
    assert outcome.failure is not None and outcome.failure.code == "model.input_denied"
    assert model.requests == [] and clients.paths == []


@pytest.mark.asyncio
async def test_business_failure_does_not_call_enabled_knowledge() -> None:
    class FailingBusinessModel:
        def __init__(self) -> None:
            self.requests: list[StructuredModelRequest] = []

        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            assert call_deadline > asyncio.get_running_loop().time()
            self.requests.append(request)
            assert request.task_id is ModelTaskId.BUSINESS_QUERY_PLAN
            raise ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)

    model, clients = FailingBusinessModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "帮我查一下在上海的员工"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert len(model.requests) == 1 and model.requests[0].task_id is ModelTaskId.BUSINESS_QUERY_PLAN
    assert len(clients.clients) == 3 and clients.paths == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected,code", [
    (ModelProviderFailureKind.PROVIDER_TIMEOUT, CapabilityStatus.TIMEOUT, "knowledge.rewrite_timeout"),
    (ModelProviderFailureKind.PROVIDER_FAILURE, CapabilityStatus.DOWNSTREAM_FAILURE, "knowledge.rewrite_failure"),
])
async def test_current_root_intent_failure_stops_before_all_knowledge_io(
    failure: ModelProviderFailureKind, expected: CapabilityStatus, code: str,
) -> None:
    class FailingIntentModel(MinimalModel):
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
                self.requests.append(request)
                raise ModelTransportError(failure)
            return await super().complete(request, call_deadline=call_deadline)

    model, clients = FailingIntentModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "现行增值税政策有哪些"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is expected
    assert outcome.failure is not None and outcome.failure.code == code
    assert [item.task_id for item in model.requests] == [
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    assert clients.paths == []


@pytest.mark.asyncio
async def test_current_root_model_insufficient_is_public_no_result_without_answer() -> None:
    class InsufficientModel(MinimalModel):
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
                self.requests.append(request)
                return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
                    tool_calls=(StructuredToolCall(name=SUMMARY_OUTPUT_NAME,
                        arguments_json='{"outcome":"insufficient_evidence","points":[]}'),),
                    usage_total_tokens=0)
            return await super().complete(request, call_deadline=call_deadline)

    model, clients = InsufficientModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "现行增值税政策有哪些"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.NO_RESULT
    assert outcome.user_result == {"reason": "insufficient_evidence"}
    assert outcome.answer_text == "已检索到资料，但不足以完整回答此问题。"
    assert [item.task_id for item in model.requests] == [
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY]


def test_disabled_current_root_does_not_create_knowledge_client() -> None:
    calls = 0
    def forbidden(_origin: str) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("disabled created Knowledge client")
    build_runtime({"AGENT_KNOWLEDGE_ENABLED": "false", "AGENT_KNOWLEDGE_ES_BASE_URL": "invalid",
                   "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "bad",
                   "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,"},
                  knowledge_http_client_factory=forbidden)
    assert calls == 0


def test_enabled_current_root_stub_without_fake_rejects_before_client_allocation() -> None:
    calls = 0

    def forbidden(_origin: str) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("invalid stub allocated Knowledge client")

    with pytest.raises(ValueError, match="knowledge.stub_transport_required"):
        build_runtime(_enabled_environment(), knowledge_http_client_factory=forbidden)
    assert calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["lookup", "explanation", "applicability"])
async def test_current_root_preserves_original_question_and_mode_through_summary(mode: str) -> None:
    question = "2025年纳税人不适用13%税率的条款是什么？"
    model, clients = MinimalModel({"outcome": "search", "query_mode": mode,
        "domains": {"tax.policy": "selected"}, "missing_conditions": []}), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
    intent_input = json.loads(model.requests[1].user_payload_json)
    summary_input = json.loads(model.requests[2].user_payload_json)
    assert intent_input["question"] == summary_input["question"] == question
    assert summary_input["query_mode"] == mode
    assert "queries" not in intent_input and "requirements" not in summary_input
    assert outcome.user_result is not None
    assert outcome.user_result["summaryType"] == (
        "extractive_evidence" if mode == "lookup" else "cited_limited_answer"
    )


@pytest.mark.asyncio
async def test_current_root_clarification_has_zero_retrieval_and_summary() -> None:
    model, clients = MinimalModel({"outcome": "clarification_required", "query_mode": "applicability",
        "domains": {"tax.policy": "not_selected"}, "missing_conditions": ["period"]}), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    try:
        question = "税收政策适用吗？"
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.NO_RESULT
    assert outcome.user_result == {"reason": "clarification_required",
                                   "selected_domain_ids": (), "coverage_complete": False}
    assert len(model.requests) == 2 and clients.paths == []


@pytest.mark.asyncio
async def test_current_root_tightened_candidate_limits_reach_typed_paths() -> None:
    class LimitClients(_KnowledgeClientFactory):
        def __init__(self) -> None:
            super().__init__()
            self.limits: list[int] = []

        def _search_result(self, request: dict[str, object]) -> dict[str, object]:
            self.limits.append(request["limit"])  # type: ignore[arg-type]
            return super()._search_result(request)

    model, clients = MinimalModel(), LimitClients()
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "5",
        "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "3"}, model_transport=model,
        knowledge_http_client_factory=clients)
    try:
        question = "现行增值税政策有哪些"
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
    assert clients.limits == [5, 5]


def test_current_root_rejects_mismatched_task_before_knowledge_clients(monkeypatch) -> None:
    original = KnowledgeQueryIntentTaskV12.definition
    monkeypatch.setattr(KnowledgeQueryIntentTaskV12, "definition", staticmethod(
        lambda **kwargs: replace(original(**kwargs), task_version="11")))
    allocated = 0

    def forbidden(_origin: str) -> object:
        nonlocal allocated
        allocated += 1
        raise AssertionError("invalid binding allocated Knowledge client")

    with pytest.raises(ValueError, match="knowledge.production_task_version_invalid"):
        build_runtime(_enabled_environment(), model_transport=MinimalModel(),
                      knowledge_http_client_factory=forbidden)
    assert allocated == 0


@pytest.mark.asyncio
async def test_current_root_concurrent_questions_keep_summary_input_request_local() -> None:
    class ConcurrentModel(MinimalModel):
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            await asyncio.sleep(0)
            return await super().complete(request, call_deadline=call_deadline)

    model, clients = ConcurrentModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    questions = ("2025年税务政策是什么？", "2024年税务政策是什么？")
    try:
        outcomes = await asyncio.gather(*(runtime.ainvoke(question=q, scope=scope(q)) for q in questions))
    finally:
        await runtime.aclose()
    assert all(item.status is CapabilityStatus.SUCCESS for item in outcomes)
    assert {json.loads(request.user_payload_json)["question"] for request in model.requests
            if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY} == set(questions)
    assert len([request for request in model.requests if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE]) == 2
    assert all(item.is_closed for item in clients.clients)


@pytest.mark.asyncio
async def test_current_root_cancellation_aborts_summary_and_closes_clients() -> None:
    class CountingClients(_KnowledgeClientFactory):
        def __init__(self) -> None:
            super().__init__()
            self.close_counts: dict[int, int] = {}

        def __call__(self, base_url: str):
            client = super().__call__(base_url)
            client_id = id(client)
            self.close_counts[client_id] = 0
            original_close = client.aclose

            async def counted_close() -> None:
                self.close_counts[client_id] += 1
                await original_close()

            setattr(client, "aclose", counted_close)
            return client

    class SlowSummaryModel(MinimalModel):
        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()
            self.released = asyncio.Event()

        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
                self.requests.append(request)
                self.entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    self.released.set()
                raise AssertionError("cancelled summary resumed")
            return await super().complete(request, call_deadline=call_deadline)

    model, clients = SlowSummaryModel(), CountingClients()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    question = "现行增值税政策有哪些"
    pending = asyncio.create_task(runtime.ainvoke(question=question, scope=scope(question)))
    await asyncio.wait_for(model.entered.wait(), timeout=2)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    await runtime.aclose()
    await runtime.aclose()
    assert model.released.is_set()
    assert [request.task_id for request in model.requests] == [
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY]
    assert all(item.is_closed for item in clients.clients)
    assert len(clients.close_counts) == 3 and set(clients.close_counts.values()) == {1}
