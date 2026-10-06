from __future__ import annotations

from dataclasses import replace
import json

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.contracts import EvidenceEgressDenialReason, EvidenceStageKind
from agent_runtime.main import build_runtime
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelProviderFailureKind, ModelTaskId, ModelTransportError, QuestionEgressDisposition,
    StructuredFinishKind,
    StructuredModelRequest, StructuredModelResponse,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.helpers import scope
from tests.integration.knowledge.test_evidence_stage import _context
from tests.integration.knowledge.test_minimal_current_root import MinimalModel
from tests.integration.knowledge.test_summary_v9_stage import FakeGateway, _stage
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory, _enabled_environment
from tests.model_helpers import call_with_model_context
from tests.unit.knowledge.evidence.test_minimal_selection import minimal_input


class RecordingKnowledgeClients(_KnowledgeClientFactory):
    def __init__(self) -> None:
        super().__init__()
        self.search_requests: list[dict[str, object]] = []
        self.embed_inputs: list[str] = []
        self.rerank_inputs: list[str] = []

    def __call__(self, base_url: str) -> httpx.AsyncClient:
        client = super().__call__(base_url)

        async def record(request: httpx.Request) -> None:
            payload = json.loads(request.content)
            if request.url.path == "/es/knowledge/search":
                assert isinstance(payload, dict)
                self.search_requests.append(payload)
            elif request.url.path == "/embed":
                self.embed_inputs.append(payload["texts"][0])
            elif request.url.path == "/rerank":
                self.rerank_inputs.append(payload["query"])

        client.event_hooks["request"].append(record)
        return client


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "现行增值税\x00政策有哪些？",
    "现行增值税\u200b政策有哪些？",
    "今天天气如何？",
])
async def test_current_root_control_or_unclassified_question_never_calls_model_or_knowledge(
    question: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    business_calls = 0

    async def forbidden_business_send(self: object, request: object) -> object:
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("denied question invoked Business HTTP")

    monkeypatch.setattr("agent_runtime.main.HttpxBusinessDomainTransport.send", forbidden_business_send)
    model, clients = MinimalModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.MODEL_EGRESS_DENIED
    assert outcome.failure is not None and outcome.failure.code == "model.input_denied"
    assert model.requests == [] and clients.paths == [] and business_calls == 0


@pytest.mark.asyncio
async def test_current_root_guard_allowed_non_capability_question_is_unsupported_without_downstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question = "如何维修税控打印机？"
    guard = QuestionEgressGuard()
    assert guard.evaluate(question).disposition is QuestionEgressDisposition.ALLOWED
    assert not guard.is_business_question(question)

    class UnsupportedActionModel(MinimalModel):
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            self.requests.append(request)
            assert request.task_id is ModelTaskId.ACTION_SELECTION
            return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP,
                content='{"capability_id":"agent_unsupported"}', tool_calls=(), usage_total_tokens=0)

    business_calls = 0

    async def forbidden_business_send(self: object, request: object) -> object:
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("unsupported question invoked Business HTTP")

    monkeypatch.setattr("agent_runtime.main.HttpxBusinessDomainTransport.send", forbidden_business_send)
    model, clients = UnsupportedActionModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.UNSUPPORTED
    assert outcome.failure is not None and outcome.failure.code == "core.no_supported_capability_candidate"
    assert [request.task_id for request in model.requests] == [ModelTaskId.ACTION_SELECTION]
    assert clients.paths == [] and business_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_task", [ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY])
async def test_current_root_knowledge_failure_never_falls_back_to_business(
    monkeypatch: pytest.MonkeyPatch, failing_task: ModelTaskId,
) -> None:
    class CountingBusinessTransport:
        def __init__(self) -> None:
            self.calls = 0

        async def send(self, request: object) -> object:
            self.calls += 1
            raise AssertionError("Knowledge failure invoked Business HTTP")

        async def aclose(self) -> None:
            pass

    business: list[CountingBusinessTransport] = []

    def business_transport_factory(**kwargs: object) -> CountingBusinessTransport:
        assert "base_endpoint" in kwargs and "allowed_paths" in kwargs
        transport = CountingBusinessTransport()
        business.append(transport)
        return transport

    class FailingKnowledgeModel(MinimalModel):
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            if request.task_id is failing_task:
                self.requests.append(request)
                raise ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
            return await super().complete(request, call_deadline=call_deadline)

    monkeypatch.setattr("agent_runtime.main.HttpxBusinessDomainTransport", business_transport_factory)
    model, clients = FailingKnowledgeModel(), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    question = "现行增值税政策有哪些？"
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert len(business) == 2 and [item.calls for item in business] == [0, 0]
    expected = [ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    if failing_task is ModelTaskId.KNOWLEDGE_SUMMARY:
        expected.append(ModelTaskId.KNOWLEDGE_SUMMARY)
    assert [item.task_id for item in model.requests] == expected
    assert clients.paths.count("/es/knowledge/search") == (0 if failing_task is ModelTaskId.KNOWLEDGE_REWRITE else 2)


@pytest.mark.asyncio
async def test_current_root_preserves_article_and_negation_in_each_typed_search_and_summary() -> None:
    question = "2025年一般纳税人是否不适用增值税暂行条例第十五条的13%税率？"
    model, clients = MinimalModel(), RecordingKnowledgeClients()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
    assert len(clients.search_requests) == 2
    assert {item["path"] for item in clients.search_requests} == {"keyword", "vector"}
    assert [item["queryText"] for item in clients.search_requests if item["path"] == "keyword"] == [question]
    assert all(item["queryText"] is None for item in clients.search_requests if item["path"] == "vector")
    assert clients.embed_inputs == [question]
    assert clients.rerank_inputs == [question]
    assert json.loads(model.requests[1].user_payload_json)["question"] == question
    assert json.loads(model.requests[2].user_payload_json)["question"] == question


@pytest.mark.asyncio
@pytest.mark.parametrize("question,selected,expected", [
    ("现行增值税政策有哪些？", ("tax.policy",), (("tax.policy", "keyword"), ("tax.policy", "vector"))),
    ("增值税法律条文有哪些？", ("tax.law",), (("tax.law", "keyword"), ("tax.law", "vector"))),
    ("增值税政策与法律条文分别有哪些？", ("tax.policy", "tax.law"),
     (("tax.policy", "keyword"), ("tax.policy", "vector"), ("tax.law", "keyword"), ("tax.law", "vector"))),
])
async def test_current_root_typed_search_paths_match_selected_domains_in_catalog_order(
    question: str, selected: tuple[str, ...], expected: tuple[tuple[str, str], ...],
) -> None:
    intent: dict[str, object] = {"outcome": "search", "query_mode": "lookup", "missing_conditions": [],
              "domains": {domain: "selected" if domain in selected else "not_selected"
                          for domain in ("tax.policy", "tax.law")}}
    model, clients = MinimalModel(intent), RecordingKnowledgeClients()
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
                            model_transport=model, knowledge_http_client_factory=clients)
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
    assert tuple((str(item["logicalDomainId"]), str(item["path"]))
                 for item in clients.search_requests) == expected
    assert clients.paths.count("/embed") == 1
    assert clients.rerank_inputs == [question] * len(selected)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["policy_version_conflict", "document_policy_conflict"])
async def test_minimal_evidence_policy_conflict_denies_before_summary(fault: str) -> None:
    gateway = FakeGateway()
    source = minimal_input()
    if fault == "policy_version_conflict":
        source = replace(source, question_policy_version="different-policy-version")
    else:
        ranked = source.batch.candidates[0]
        source = replace(source, batch=replace(source.batch, candidates=(replace(ranked,
            candidate=replace(ranked.candidate, policy_ref="different-policy-ref")),)))
    result = await call_with_model_context(lambda: _stage(gateway).build_result(
        input=source, context=_context(), timeout_s=2))
    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.denial_reason is EvidenceEgressDenialReason.POLICY_CONFLICT
    assert result.domain_result is None and gateway.inputs == []
