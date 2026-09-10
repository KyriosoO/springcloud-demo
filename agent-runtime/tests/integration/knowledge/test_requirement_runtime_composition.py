"""Actual 9/7/v3 production root, synthetic transports; not live effectiveness."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3
from agent_runtime.knowledge.evidence.contracts import KnowledgeRequirementSummaryInput
from agent_runtime.knowledge.evidence.summary_task_v5 import KnowledgeSummaryTaskV5
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v6 import KnowledgeRewriteTaskV6
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId, StructuredFinishKind, StructuredModelResponse
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _FixedStream, _KnowledgeClientFactory, _enabled_environment


QUESTION = "税务测试资料中乙类服务在指定期间如何适用规则？"
FOCUSES = ("税务服务分类依据", "税务适用规则依据", "税务规则施行依据")
CONTENTS = ("合成税务资料：乙类属于甲类服务。", "合成税务资料：甲类服务执行标准规则。", "合成税务资料：本规则自指定期间施行。")


def plan(*, multi=False, applicability=True, question=QUESTION):
    domains = ("tax.policy", "tax.law") if multi else ("tax.policy",)
    kinds = ("subject_scope", "rule", "temporal_scope") if applicability else ("rule",)
    return {"outcome": "search", "question_kind": "applicability" if applicability else "lookup",
        "queries": [{"domain_id": d, "query": question} for d in domains],
        "requirements": [{"requirement_id": f"r{i}", "domain_id": domains[-1] if i > 1 else domains[0],
                          "kind": kind, "focus": FOCUSES[i - 1]} for i, kind in enumerate(kinds, 1)],
        "missing_conditions": []}


class Model:
    def __init__(self, output, *, fault=None):
        self.output, self.fault, self.requests = output, fault, []
        self.entered, self.released = asyncio.Event(), asyncio.Event()

    async def complete(self, request, *, call_deadline):
        assert call_deadline > asyncio.get_running_loop().time()
        self.requests.append(request)
        payload = json.loads(request.user_payload_json)
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            value = {"capability_id": "knowledge.query"}
            if self.fault == "second_action": value["second"] = "employee.search"
        elif request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            assert request.task_version == "9" and request.max_output_tokens == 1536
            if self.fault == "rewrite_failure": raise RuntimeError("synthetic")
            if self.fault == "rewrite_timeout": raise TimeoutError("synthetic")
            value = deepcopy(self.output)
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            assert request.task_version == "7" and payload["schema_version"] == 2
            if self.fault == "summary_failure": raise RuntimeError("synthetic")
            if self.fault == "summary_timeout": raise TimeoutError("synthetic")
            if self.fault == "wait":
                self.entered.set()
                try: await asyncio.Event().wait()
                finally: self.released.set()
            by_content = {e["content"]: e["evidence_ref"] for e in payload["evidence"]}
            coverage, points = [], []
            for i, requirement in enumerate(payload["requirements"]):
                ref = by_content[CONTENTS[i]]
                points.append({"evidence_ref": ref, "quote": CONTENTS[i]})
                coverage.append({"requirement_id": requirement["requirement_id"], "evidence_refs": [ref]})
            value = {"outcome": "answer", "points": points, "coverage": coverage}
            if self.fault == "missing_coverage": value["coverage"] = coverage[:-1]
            elif self.fault == "unknown_ref": value["coverage"][0]["evidence_refs"] = ["e8"]
            elif self.fault == "wrong_domain": value["coverage"][0]["evidence_refs"] = [points[-1]["evidence_ref"]]
            elif self.fault == "quote": value["points"][0]["quote"] = "不在原文的内容"
            elif self.fault == "duplicate": value["points"].append(points[0])
            elif self.fault == "insufficient": value = {"outcome": "insufficient_evidence", "points": [], "coverage": []}
        else:
            raise AssertionError("No Business or answer model task")
        return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content=json.dumps(value, ensure_ascii=False),
            tool_calls=(), usage_total_tokens=0)


class Clients(_KnowledgeClientFactory):
    def __init__(self, *, multi=False, fault=None):
        super().__init__()
        self.multi, self.fault, self.payloads = multi, fault, []

    def __call__(self, base_url):
        async def handle(request):
            value = json.loads(request.content)
            self.paths.append(request.url.path)
            self.payloads.append((request.url.path, value))
            if request.url.path == "/embed": return self._json({"dim": 1024, "vectors": [[0.0] * 1024]})
            if request.url.path == "/rerank":
                if self.fault == "rerank": return httpx.Response(500, stream=_FixedStream(b""))
                top = CONTENTS[FOCUSES.index(value["query"])]
                scoring_top = top + "\n文档标题：增值税政策资料" + str(CONTENTS.index(top) + 1)
                return self._json({"model": "BAAI/bge-reranker-v2-m3", "results": [
                    {"index": i, "text": text, "score": 1.0 if text == scoring_top else 0.0}
                    for i, text in enumerate(value["documents"])]})
            assert request.url.path == "/es/knowledge/search"
            self.es_authorizations.append(request.headers["Authorization"])
            if self.fault == "denied": return httpx.Response(403, stream=_FixedStream(b""))
            if self.fault == "all_failed" or self.fault == "partial" and value["path"] == "vector":
                return httpx.Response(500, stream=_FixedStream(b""))
            result = super(Clients, self)._search_result(value)
            for item, content in zip(result["candidates"], CONTENTS, strict=True):
                item.update(content=content, contentSha256=hashlib.sha256(content.encode()).hexdigest())
                if self.fault == "policy": item["policyRef"] = "unclassified"
            if self.multi:
                result["candidates"] = result["candidates"][:1] if value["logicalDomainId"] == "tax.policy" else result["candidates"][1:]
                for rank, candidate in enumerate(result["candidates"], 1): candidate["sourceRank"] = rank
            if self.fault == "empty": result["candidates"] = []
            if self.fault == "profile": result["profileVersion"] = "unexpected"
            return self._json(result)
        client = httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handle), trust_env=False)
        self.clients.append(client)
        return client


async def invoke(output=None, *, model_fault=None, client_fault=None, multi=False, question=QUESTION, monkeypatch=None):
    calls = []
    if monkeypatch:
        async def forbidden_business(self, outbound):
            calls.append(outbound)
            raise AssertionError("Business transport forbidden")
        monkeypatch.setattr(HttpxBusinessDomainTransport, "send", forbidden_business)
    model, clients = Model(output or plan(multi=multi), fault=model_fault), Clients(multi=multi, fault=client_fault)
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
        model_transport=model, knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            outcome = await runtime.ainvoke(question=question, scope=scope(question))
            observation = collector.snapshot()
    finally:
        await runtime.aclose()
        await runtime.aclose()
    assert not calls and all(client.is_closed for client in clients.clients)
    return outcome, model, clients, observation


@pytest.mark.asyncio
@pytest.mark.parametrize("multi", [False, True])
async def test_current_root_retains_three_proof_anchors_and_summary_coverage(multi, monkeypatch, caplog):
    result, model, clients, observation = await invoke(multi=multi, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS, result.failure
    assert result.capability_id == "knowledge.query" and [p["quote"] for p in result.user_result["points"]] == list(CONTENTS)
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"), (ModelTaskId.KNOWLEDGE_REWRITE, "9"), (ModelTaskId.KNOWLEDGE_SUMMARY, "7")]
    assert [v["query"] for p, v in clients.payloads if p == "/rerank"] == list(FOCUSES)
    expected_documents = [text + "\n文档标题：增值税政策资料" + str(i) for i, text in enumerate(CONTENTS, 1)]
    for path, body in clients.payloads:
        if path == "/rerank":
            assert body["documents"] == (expected_documents[:1] if multi and body["query"] == FOCUSES[0]
                else expected_documents[1:] if multi else expected_documents)
    assert clients.paths.count("/es/knowledge/search") == (4 if multi else 2)
    assert clients.paths.count("/embed") == 1 and clients.paths.count("/rerank") == 3
    assert len(observation.plans) == 1 and observation.plans[0]["plan"]["quality_version"] == KNOWLEDGE_QUALITY_VERSION_V3
    assert clients.es_authorizations == ["Bearer header.payload.signature"] * (4 if multi else 2)
    payload = json.loads(model.requests[-1].user_payload_json)
    assert payload["question"] == QUESTION and payload["requirements"] == plan(multi=multi)["requirements"]
    visible = json.dumps(asdict(observation), ensure_ascii=False) + caplog.text
    assert all(text not in visible for text in CONTENTS + FOCUSES)
    assert "文档标题：" not in visible and "成文日期（非生效日期）" not in visible
    assert "header.payload.signature" not in visible
    assert all("header.payload.signature" not in r.user_payload_json for r in model.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected,summary_calls", [
    ("empty", CapabilityStatus.NO_RESULT, 0), ("all_failed", CapabilityStatus.DOWNSTREAM_FAILURE, 0),
    ("partial", CapabilityStatus.SUCCESS, 1), ("denied", CapabilityStatus.FORBIDDEN, 0),
    ("policy", CapabilityStatus.MODEL_EGRESS_DENIED, 0), ("profile", CapabilityStatus.DOWNSTREAM_FAILURE, 0),
    ("rerank", CapabilityStatus.DOWNSTREAM_FAILURE, 0),
])
async def test_retrieval_failures_never_fallback_or_masquerade_as_empty(fault, expected, summary_calls, monkeypatch):
    result, model, clients, _ = await invoke(client_fault=fault, monkeypatch=monkeypatch)
    assert result.status is expected, result.failure
    assert sum(r.task_id is ModelTaskId.KNOWLEDGE_SUMMARY for r in model.requests) == summary_calls
    assert clients.paths.count("/es/knowledge/search") == 2
    if fault == "partial": assert result.user_result["coverage"]["retrievalComplete"] is False
    if fault in {"denied", "profile", "all_failed", "empty"}: assert "/rerank" not in clients.paths


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected,total", [
    ("rewrite_failure", CapabilityStatus.DOWNSTREAM_FAILURE, 2), ("rewrite_timeout", CapabilityStatus.TIMEOUT, 2),
    ("second_action", CapabilityStatus.DOWNSTREAM_FAILURE, 1),
    ("summary_failure", CapabilityStatus.DOWNSTREAM_FAILURE, 3), ("summary_timeout", CapabilityStatus.TIMEOUT, 3),
    ("missing_coverage", CapabilityStatus.DOWNSTREAM_FAILURE, 3), ("unknown_ref", CapabilityStatus.DOWNSTREAM_FAILURE, 3),
    ("wrong_domain", CapabilityStatus.DOWNSTREAM_FAILURE, 3), ("quote", CapabilityStatus.DOWNSTREAM_FAILURE, 3),
    ("duplicate", CapabilityStatus.DOWNSTREAM_FAILURE, 3), ("insufficient", CapabilityStatus.NO_RESULT, 3),
])
async def test_model_and_coverage_fail_closed_without_second_action(fault, expected, total, monkeypatch):
    result, model, clients, _ = await invoke(model_fault=fault, multi=fault == "wrong_domain", monkeypatch=monkeypatch)
    assert result.status is expected, result.failure
    assert len(model.requests) == total
    if total < 3: assert not clients.paths
    if fault == "insufficient": assert result.user_result["reason"] == "insufficient_evidence"


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["old_schema", "no_req", "unknown_domain", "unknown_kind", "unsafe_focus", "new_ratio", "new_date", "duplicate_req", "missing_role", "extra_field"])
async def test_invalid_plan_zero_retrieval_and_zero_summary(fault):
    value = plan()
    if fault == "old_schema": value.pop("requirements"); value.pop("question_kind")
    elif fault == "no_req": value["requirements"] = []
    elif fault == "unknown_domain": value["requirements"][0]["domain_id"] = "not.enabled"
    elif fault == "unknown_kind": value["requirements"][0]["kind"] = "invented"
    elif fault == "unsafe_focus": value["requirements"][0]["focus"] = "税务someone@example.com."
    elif fault == "new_ratio": value["requirements"][0]["focus"] = "税务6%规则"
    elif fault == "new_date": value["requirements"][0]["focus"] = "税务2027年规则"
    elif fault == "duplicate_req": value["requirements"][1]["requirement_id"] = "r1"
    elif fault == "missing_role": value["requirements"] = value["requirements"][:1]
    else: value["extra"] = True
    result, model, clients, observation = await invoke(value)
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE and len(model.requests) == 2
    assert not clients.paths and not observation.plans and not observation.downstream_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,missing,reason", [("unsupported", [], "no_matching_domain"), ("clarification_required", ["taxpayer_type"], "clarification_required")])
async def test_terminal_plan_no_retrieval_or_summary(outcome, missing, reason):
    result, model, clients, _ = await invoke({"outcome": outcome, "question_kind": "none", "queries": [], "requirements": [], "missing_conditions": missing})
    assert result.status is CapabilityStatus.NO_RESULT and result.user_result["reason"] == reason
    assert len(model.requests) == 2 and clients.paths == []


@pytest.mark.asyncio
async def test_sensitive_question_has_zero_model_and_domain_calls():
    result, model, clients, _ = await invoke(question="税务someone@example.com.")
    assert result.status is CapabilityStatus.MODEL_EGRESS_DENIED and not model.requests and not clients.paths


@pytest.mark.parametrize("domains", ["tax.policy", "tax.policy,tax.law"])
def test_minimum_four_checked_before_any_client_or_model_factory(domains, monkeypatch):
    from agent_runtime import main
    def forbidden(*args, **kwargs): raise AssertionError("No client/model may be allocated")
    monkeypatch.setattr(main.LocalModelCompositionRoot, "build", forbidden)
    monkeypatch.setattr(main, "HttpxBusinessDomainTransport", forbidden)
    with pytest.raises(ValueError, match="cannot_cover_domain_anchors"):
        build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": domains,
                       "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "3"}, model_transport=Model(plan()), knowledge_http_client_factory=forbidden)


@pytest.mark.parametrize("fault", ["rewrite_version", "summary_version", "summary_six", "summary_unknown", "rewrite_id", "summary_id", "rewrite_type", "summary_type"])
def test_production_rejects_mixed_task_pair_before_model_use(fault):
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks.rewrite.task_version == "9" and tasks.summary.task_version == "7"
    if fault == "rewrite_version": tasks = replace(tasks, rewrite=KnowledgeRewriteTaskV6.definition())
    elif fault == "summary_version": tasks = replace(tasks, summary=KnowledgeSummaryTaskV5.definition())
    elif fault in {"summary_six", "summary_unknown"}:
        tasks = replace(tasks, summary=replace(tasks.summary, task_version="6" if fault == "summary_six" else "999"))
    elif fault == "rewrite_id": tasks = replace(tasks, rewrite=replace(tasks.rewrite, task_id=ModelTaskId.KNOWLEDGE_SUMMARY))
    elif fault == "summary_id": tasks = replace(tasks, summary=replace(tasks.summary, task_id=ModelTaskId.KNOWLEDGE_REWRITE))
    elif fault == "rewrite_type": tasks = replace(tasks, rewrite=replace(tasks.rewrite, input_type=KnowledgeRequirementSummaryInput))
    else: tasks = replace(tasks, summary=replace(tasks.summary, input_type=KnowledgeSemanticPlanInput))
    with pytest.raises(ValueError, match="production_task_version_invalid"):
        KnowledgeCompositionRoot.build_provider(settings=KnowledgeSettings.from_env(_enabled_environment()), model=None,
            tasks=tasks, retrieval=object())


@pytest.mark.asyncio
async def test_current_root_cancel_closes_all_clients_without_summary_retry():
    model, clients = Model(plan(), fault="wait"), Clients()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)
    task = asyncio.create_task(runtime.ainvoke(question=QUESTION, scope=scope(QUESTION)))
    await asyncio.wait_for(model.entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    await runtime.aclose()
    assert model.released.is_set() and len(model.requests) == 3 and all(c.is_closed for c in clients.clients)


def test_historical_root_isolation_is_exact_scoped_and_restored(monkeypatch):
    from agent_runtime import bootstrap, main
    from tests.integration.knowledge.conftest import isolate_version_specific_knowledge_root, legacy_root

    current = bootstrap.KnowledgeCompositionRoot
    parent = Path(__file__).resolve().parent
    for path, expected in ((Path(__file__), current), (parent.parent / "test_stage_b_production.py", current),
                           (parent / "test_stage_b_production.py", legacy_root())):
        module = SimpleNamespace(__file__=str(path), KnowledgeCompositionRoot=current)
        with monkeypatch.context() as patch:
            isolate_version_specific_knowledge_root.__wrapped__(SimpleNamespace(module=module), patch)
            assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is expected
            assert module.KnowledgeCompositionRoot is expected
        assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is current
    assert legacy_root().task_definitions(enabled=True).rewrite.task_version == "6"
    assert current.task_definitions(enabled=True).rewrite.task_version == "9"


@pytest.mark.asyncio
async def test_current_disabled_root_never_constructs_knowledge_dependencies():
    def forbidden(*args): raise AssertionError("Knowledge dependency while disabled")
    runtime = build_runtime({"AGENT_KNOWLEDGE_ENABLED": "false", "AGENT_KNOWLEDGE_ES_BASE_URL": "invalid"},
                            knowledge_http_client_factory=forbidden)
    outcome = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
    assert outcome.status is CapabilityStatus.UNSUPPORTED
    # The dependency-free stub owns no closeable resources.
    assert not hasattr(runtime, "aclose")


@pytest.mark.asyncio
async def test_current_root_keeps_concurrent_requirement_state_request_local():
    questions = (QUESTION, "税务测试资料中甲类服务在指定期间如何适用规则？")

    class ConcurrentModel(Model):
        async def complete(self, request, *, call_deadline):
            if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
                question = json.loads(request.user_payload_json)["question"]
                await asyncio.sleep(0)
                return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP,
                    content=json.dumps(plan(question=question)), tool_calls=(), usage_total_tokens=0)
            return await super().complete(request, call_deadline=call_deadline)

    model, clients = ConcurrentModel(plan()), Clients()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)
    try:
        results = await asyncio.gather(*(runtime.ainvoke(question=q, scope=scope(q)) for q in questions))
        assert all(result.status is CapabilityStatus.SUCCESS for result in results)
        summaries = [json.loads(r.user_payload_json) for r in model.requests if r.task_id is ModelTaskId.KNOWLEDGE_SUMMARY]
        assert {value["question"] for value in summaries} == set(questions)
        assert all(value["requirements"] == plan()["requirements"] for value in summaries)
    finally:
        await runtime.aclose()
    assert all(client.is_closed for client in clients.clients) and clients.paths.count("/es/knowledge/search") == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "outer", "rewrite_shape", "summary_shape"])
async def test_current_wire_provider_and_two_task_decoders_are_not_bypassed(fault, caplog):
    from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
    from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
    from tests.integration.knowledge.test_rewrite_v4_provider_boundary import _envelope

    calls, model, clients = [], Model(plan()), Clients()
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    definitions = (None, tasks.rewrite, tasks.summary)
    key = "synthetic-nonlive-requirement-wire-key"

    async def handle(request):
        assert str(request.url) == ModelSettings.BASE_URL + "/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + key
        payload = json.loads(request.content)
        index = len(calls)
        calls.append(payload)
        assert payload["response_format"] == {"type": "json_object"} and "tools" not in payload
        if index:
            assert payload["max_tokens"] == 1536
        task_id = (ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY)[index]
        response = await model.complete(SimpleNamespace(task_id=task_id,
            task_version=definitions[index].task_version if index else "action-selection-v4",
            max_output_tokens=payload["max_tokens"], user_payload_json=payload["messages"][1]["content"]),
            call_deadline=asyncio.get_running_loop().time() + 5)
        value = json.loads(response.content)
        if fault == "rewrite_shape" and index == 1:
            value.pop("requirements")
        if fault == "summary_shape" and index == 2:
            value.pop("coverage")
        envelope = _envelope(json.dumps(value, ensure_ascii=False))
        if fault == "outer" and index == 1:
            envelope["model"] = "incorrect-provider-model"
        return clients._json(envelope)

    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(key))
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handle), trust_env=False) as http:
        runtime = build_runtime(_enabled_environment(), knowledge_http_client_factory=clients,
            model_transport=DeepSeekChatTransport(settings=settings, client=http))
        try:
            with observation_scope() as collector:
                result = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
                visible = json.dumps(asdict(collector.snapshot()), ensure_ascii=False)
        finally:
            await runtime.aclose()
    assert result.status is (CapabilityStatus.SUCCESS if fault is None else CapabilityStatus.DOWNSTREAM_FAILURE)
    assert len(calls) == (2 if fault in {"outer", "rewrite_shape"} else 3)
    if len(calls) == 2: assert clients.paths == []
    assert all(client.is_closed for client in clients.clients)
    assert key not in visible + caplog.text and all(value not in visible for value in CONTENTS + FOCUSES)


@pytest.mark.parametrize("task", ["rewrite", "summary"])
def test_task_factory_version_error_precedes_client_allocation(task, monkeypatch):
    from agent_runtime import main
    from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
    from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7
    def forbidden(*args, **kwargs): raise AssertionError("No resources before configuration validation")
    monkeypatch.setattr(main.LocalModelCompositionRoot, "build", forbidden)
    monkeypatch.setattr(main, "HttpxBusinessDomainTransport", forbidden)
    if task == "rewrite":
        monkeypatch.setattr(KnowledgeRewriteTaskV9, "definition", KnowledgeRewriteTaskV6.definition)
    else:
        monkeypatch.setattr(KnowledgeSummaryTaskV7, "definition", KnowledgeSummaryTaskV5.definition)
    with pytest.raises(ValueError, match="production_task_version_invalid"):
        build_runtime(_enabled_environment(), model_transport=Model(plan()), knowledge_http_client_factory=forbidden)
