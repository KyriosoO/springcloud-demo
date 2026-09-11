"""V11 component pipeline with real decoders and fake I/O, not a live/root claim."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.contracts import (
    DomainSelection, KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeQueryArguments, RewriteStageKind,
)
from agent_runtime.knowledge.document_reference_semantics import DocumentReferenceSemanticGuard
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.retrieval.contracts import PathResultKind
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.knowledge.rewrite_v11 import KnowledgeRewriteTaskV11, OUTPUT_NAME
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.contracts import ModelCallContext
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from agent_runtime.observation import observation_scope
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v11 import DOMAINS, slotted
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory
from tests.integration.knowledge.test_rewrite_v4_provider_boundary import _envelope
from tests.unit.knowledge.retrieval.test_stage import FakeEmbedding, FakeRerank, FakeSearch
from tests.unit.knowledge.test_query_constraint_scope import LAW_QUERY, POLICY_QUERY, QUESTION
from tests.unit.knowledge.test_semantic_planner_v9 import wire

KEY = "synthetic-nonlive-v11-key"


def planner(gateway, *, domains=DOMAINS, definition=None):
    return KnowledgeSemanticPlanner(
        gateway=gateway, context=SimpleNamespace(require_current=lambda: ModelCallContext(
            request_id="nonlive-r", correlation_id="nonlive-c",
            deadline_monotonic=asyncio.get_running_loop().time() + 10,
        )), enabled_domain_ids=domains,
        definition=definition or KnowledgeRewriteTaskV11.definition(enabled_domain_ids=domains),
        quality_version=KNOWLEDGE_QUALITY_VERSION_V3, semantic_guard=DocumentReferenceSemanticGuard(),
    )


class EmptySearch(FakeSearch):
    async def search(self, **kwargs):
        result = await super().search(**kwargs)
        return replace(result, kind=PathResultKind.NO_RESULT, candidates=())


class NoEvidence:
    calls = 0

    async def build_result(self, **kwargs):
        self.calls += 1
        raise AssertionError("No Evidence or Summary without retrieval results")


async def invoke(value, *, raw=None, question=QUESTION, domains=DOMAINS, fault=None):
    """No network: HTTP transport, gateway, task, planner and capability are real."""
    requests = []
    task = KnowledgeRewriteTaskV11.definition(enabled_domain_ids=domains)
    settings = KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ",".join(domains)})
    embedding, search, rerank, evidence = FakeEmbedding(), EmptySearch(), FakeRerank(), NoEvidence()

    async def respond(request):
        assert str(request.url) == ModelSettings.BASE_URL + "/beta/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + KEY
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["model"] == "deepseek-flash" and payload["stream"] is False
        assert payload["max_tokens"] == 1536 and payload["thinking"] == {"type": "disabled"}
        assert "response_format" not in payload and len(payload["tools"]) == 1
        schema = payload["tools"][0]["function"]["parameters"]["properties"]["queries"]
        assert set(schema["properties"]) == set(domains) and schema["required"] == list(domains)
        if fault == "timeout":
            raise httpx.ReadTimeout("synthetic")
        if fault == "cancel":
            raise asyncio.CancelledError
        if fault == "http_error":
            return httpx.Response(503)
        envelope = _envelope(None, finish_reason="tool_calls")
        envelope["choices"][0]["message"] = {"content": None, "tool_calls": [{
            "type": "function", "function": {"name": OUTPUT_NAME,
                "arguments": json.dumps(value, ensure_ascii=False) if raw is None else raw}}]}
        if fault == "outer_model":
            envelope["model"] = "incorrect-model"
        return _KnowledgeClientFactory._json(envelope)

    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(respond), trust_env=False) as http:
        gateway = BoundedStructuredModelGateway(
            transport=DeepSeekChatTransport(client=http, settings=ModelSettings(
                provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(KEY))),
            definitions=(task,), max_concurrency=1,
        )
        capability = KnowledgeQueryCapability(
            settings=settings, enabled_domains=build_tax_domain_catalog().enabled(domains),
            rewriter=planner(gateway, domains=domains, definition=task), selector=None,
            planner=KnowledgeRetrievalPlanBuilder(preserve_original_keyword=True),
            retrieval=DefaultKnowledgeRetrievalStage(embedding=embedding, search=search, rerank=rerank),
            evidence=evidence, require_semantic_plan=True,
        )
        with observation_scope() as collector:
            try:
                result = await capability.handle(KnowledgeQueryArguments(), scope(question).context)
            except asyncio.CancelledError:
                assert len(requests) == 1 and not search.calls and embedding.calls == rerank.calls == evidence.calls == 0
                raise
            observed = collector.snapshot()
    assert http.is_closed
    return result, requests, search, embedding, rerank, evidence, observed


@pytest.mark.asyncio
@pytest.mark.parametrize("domains", [DOMAINS, ("tax.policy",), ("tax.law",)])
async def test_real_provider_decoders_and_scoped_planner_reach_only_selected_domains(domains, caplog):
    value = wire()
    value["queries"] = [item for item in value["queries"] if item["domain_id"] in domains]
    value["requirements"] = [item for item in value["requirements"] if item["domain_id"] in domains]
    for i, requirement in enumerate(value["requirements"], 1):
        requirement["requirement_id"] = f"r{i}"
    question = QUESTION if len(domains) == 2 else value["queries"][0]["query"]
    result, calls, search, embedding, rerank, evidence, observed = await invoke(
        slotted(value, domains), question=question, domains=domains)
    assert result.status is CapabilityStatus.NO_RESULT, result.failure
    assert len(calls) == 1 and len(search.calls) == 2 * len(domains) and embedding.calls == len(domains)
    assert rerank.calls == evidence.calls == 0
    assert {item.logical_domain_id for item in search.calls} == set(domains)
    assert all(item.query_text == question for item in search.calls if item.query_text is not None)
    assert len(observed.plans) == 1 and observed.model_calls[0]["status"] == "succeeded"
    # Accepted internal plans may show safe queries, but no raw response/slot object.
    assert "queries" not in observed.plans[0]["plan"]
    assert "requirements" not in observed.model_calls[0]["request"]["input"]
    assert KEY not in json.dumps(asdict(observed)) + caplog.text


def invalid_wires():
    cases = []
    for slots in ([], {}, {"tax.policy": POLICY_QUERY}, {"tax.policy": POLICY_QUERY, "tax.law": None},
                  {"tax.policy": POLICY_QUERY, "tax.law": "", "employee": ""},
                  {"tax.policy": POLICY_QUERY, "tax.law": " "}, {"tax.policy": POLICY_QUERY, "tax.law": ""}):
        item = slotted(wire())
        item["queries"] = slots
        cases.append(item)
    for field, replacement in (("query", POLICY_QUERY.replace("2011", "2012")),
        ("query", LAW_QUERY), ("query", POLICY_QUERY + " 100"),
        ("focus", POLICY_QUERY.replace("100", "101")), ("focus", "税务synthetic@example.com")):
        item = slotted(wire())
        if field == "query":
            item["queries"]["tax.policy"] = replacement
        else:
            item["requirements"][0]["focus"] = replacement
        cases.append(item)
    for key, replacement in (("requirements", []), ("question_kind", "invented")):
        item = slotted(wire())
        item[key] = replacement
        cases.append(item)
    cases.append(wire())  # Real old array, no helper or fallback in the invocation.
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("value", invalid_wires())
async def test_illegal_slot_or_original_semantics_fail_before_all_downstream(value, caplog):
    result, calls, search, embedding, rerank, evidence, observed = await invoke(value)
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE, result.failure
    assert result.failure.code == "knowledge.rewrite_failure" and len(calls) == 1
    assert not search.calls and embedding.calls == rerank.calls == evidence.calls == 0
    assert observed.plans == () and observed.downstream_calls == ()
    visible = json.dumps(asdict(observed)) + caplog.text
    assert "synthetic@example.com" not in visible and KEY not in visible


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["timeout", "http_error", "outer_model", "duplicate", "cancel"])
async def test_wire_failures_and_cancel_never_retry_or_fallback(fault):
    value = slotted(wire())
    raw = json.dumps(value).replace('"tax.policy":', '"tax.policy":"tax","tax.policy":', 1) if fault == "duplicate" else None
    if fault == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await invoke(value, fault=fault)
        return
    result, calls, search, embedding, rerank, evidence, observed = await invoke(value, raw=raw, fault=fault)
    assert result.status is (CapabilityStatus.TIMEOUT if fault == "timeout" else CapabilityStatus.DOWNSTREAM_FAILURE)
    assert len(calls) == 1 and not search.calls and embedding.calls == rerank.calls == evidence.calls == 0
    assert not observed.plans and not observed.downstream_calls
    assert observed.model_calls[0]["failureKind"] == ("provider_timeout" if fault == "timeout" else
        "provider_failure" if fault == "http_error" else "invalid_output")


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,missing,reason", [("unsupported", [], "no_matching_domain"),
    ("clarification_required", ["taxpayer_type"], "clarification_required")])
async def test_all_empty_slots_keep_terminal_semantics(outcome, missing, reason):
    value = dict(outcome=outcome, question_kind="none", queries=dict.fromkeys(DOMAINS, ""), requirements=[], missing_conditions=missing)
    result, calls, search, embedding, rerank, evidence, _ = await invoke(value)
    assert result.status is CapabilityStatus.NO_RESULT and result.domain_result["reason"] == reason
    assert len(calls) == 1 and not search.calls and embedding.calls == rerank.calls == evidence.calls == 0


@pytest.mark.asyncio
async def test_sensitive_original_has_zero_wire_and_downstream_calls():
    result, calls, search, embedding, rerank, evidence, observed = await invoke(
        slotted(wire()), question="税务synthetic@example.com")
    assert result.status is CapabilityStatus.MODEL_EGRESS_DENIED
    assert not calls and not search.calls and embedding.calls == rerank.calls == evidence.calls == 0
    assert not observed.model_calls and not observed.plans


@pytest.mark.asyncio
@pytest.mark.parametrize("forgery", ["old_output", "missing_requirements", "unknown_domain", "terminal_with_queries"])
async def test_internal_gateway_cannot_bypass_semantic_output_validation(forgery):
    output = KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(wire())))
    if forgery == "old_output":
        output = KnowledgeSemanticPlanOutput(outcome="unsupported", queries=(), missing_conditions=())
    elif forgery == "missing_requirements":
        output = replace(output, evidence_requirements=())
    elif forgery == "unknown_domain":
        output = replace(output, queries=(replace(output.queries[0], domain_id="employee"), output.queries[1]))
    else:
        output = replace(output, outcome="clarification_required", missing_conditions=("taxpayer_type",))

    async def generate(**kwargs):
        return SimpleNamespace(output=output)

    result = await planner(SimpleNamespace(generate=generate)).rewrite(original_question=QUESTION, timeout_s=8)
    assert result.kind is RewriteStageKind.FAILURE and result.rewrite is None


@pytest.mark.asyncio
async def test_valid_slot_mapping_preserves_v9_retrieval_plan_and_requirement_identity():
    results = []
    for task in (KnowledgeRewriteTaskV9.definition(), KnowledgeRewriteTaskV11.definition(enabled_domain_ids=DOMAINS)):
        class Transport:
            async def complete(self, request, **kwargs):
                from tests.contract.knowledge.test_rewrite_task_v11 import response
                return _response(json.dumps(wire())) if task.task_version == "9" else response(slotted(wire()))

        gateway = BoundedStructuredModelGateway(transport=Transport(), definitions=(task,), max_concurrency=1)
        result = await planner(gateway, definition=task).rewrite(original_question=QUESTION, timeout_s=8)
        assert result.kind is RewriteStageKind.SUCCESS
        rewritten = result.rewrite
        plan = KnowledgeRetrievalPlanBuilder(preserve_original_keyword=True).build(rewrite=rewritten,
            domains=DomainSelection(selected_domain_ids=DOMAINS, catalog_version="test", reason_codes=()),
            settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ",".join(DOMAINS)}))
        assert plan.evidence_requirements is rewritten.evidence_requirements
        results.append((rewritten, plan))
    assert results[0] == results[1]
