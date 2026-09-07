"""Use the current production object graph and synthetic, memory-only transports."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.capability_api.contracts import CapabilityStatus, canonical_json_bytes
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import (
    _KnowledgeClientFactory, _KnowledgeModelTransport, _enabled_environment,
)
from tests.system_e2e.knowledge_stage_b_citation_check import check_citations


QUESTION = "税务测试资料中，甲项的规则是什么？"
CLAUSE = "共同语句。"
CONTENTS = ("合成规则甲的正文。" + CLAUSE, "合成规则乙的正文。" + CLAUSE, "合成规则丙的正文。")
# Expected source is fixed before invocation, not inferred from model output.
GOLD = {"rule": {"chunk": "chunk-1", "sha256": hashlib.sha256(CONTENTS[0].encode()).hexdigest(),
                 "clause": CLAUSE}}


class _Clients(_KnowledgeClientFactory):
    def _search_result(self, request):
        result = super()._search_result(request)
        for item, content in zip(result["candidates"], CONTENTS, strict=True):
            item["content"] = content
            item["contentSha256"] = hashlib.sha256(content.encode()).hexdigest()
        return result


class _Model(_KnowledgeModelTransport):
    def __init__(self, cited_index):
        super().__init__()
        self.cited_index = cited_index

    async def complete(self, request, *, call_deadline):
        response = await super().complete(request, call_deadline=call_deadline)
        if request.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY:
            return response
        evidence = json.loads(request.user_payload_json)["evidence"]
        assert [item["content"] for item in evidence] == list(CONTENTS)
        return replace(response, content=json.dumps({"outcome": "answer", "points": [{
            "evidence_ref": evidence[self.cited_index]["evidence_ref"], "quote": CLAUSE,
        }]}, ensure_ascii=False))


@pytest.mark.parametrize("cited_index, covered", [(0, True), (1, False)])
@pytest.mark.asyncio
async def test_actual_policy_input_and_public_citation_must_bind_the_expected_source(
    cited_index, covered, monkeypatch, caplog,
):
    captured = []
    decide = KnowledgeEvidenceEgressDecider.decide

    def capture(self, *, bundle, catalog):
        decision = decide(self, bundle=bundle, catalog=catalog)
        assert decision.allowed and decision.summary_input is not None
        captured.append((bundle, decision.summary_input))
        return decision

    business_calls = 0

    async def reject_business(self, outbound):
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("No Business call is permitted")

    monkeypatch.setattr(KnowledgeEvidenceEgressDecider, "decide", capture)
    monkeypatch.setattr(HttpxBusinessDomainTransport, "send", reject_business)
    model, clients = _Model(cited_index), _Clients()
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            outcome = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
            # Both quotes are genuinely grounded. That alone does not satisfy gold.
            assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
            assert outcome.capability_id == "knowledge.query"
            assert len(captured) == 1
            bundle, model_input = captured[0]
            payload = json.loads(model.requests[-1].user_payload_json)
            assert payload["question"] == model_input.question
            assert [(e["evidence_ref"], e["content"]) for e in payload["evidence"]] == [
                (e.evidence_ref, e.content) for e in model_input.evidence]
            points = json.loads(canonical_json_bytes(outcome.user_result))["points"]
            assert points[0]["citation"]["evidenceId"] == bundle.evidence[cited_index].evidence_id
            verdict = check_citations(bundle=bundle, summary_input=model_input, points=points, required=GOLD)
            assert verdict.binding_valid and verdict.required_clauses == (("rule", covered),)
            assert verdict.failure_reason == (None if covered else "required_source_not_cited")
            observations = collector.snapshot()
    finally:
        captured.clear()
        await runtime.aclose()
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
        (ModelTaskId.KNOWLEDGE_REWRITE, "6"), (ModelTaskId.KNOWLEDGE_SUMMARY, "5"),
    ]
    assert business_calls == 0
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/embed") == clients.paths.count("/rerank") == 1
    assert set(clients.paths) == {"/es/knowledge/search", "/embed", "/rerank"}
    visible = json.dumps(asdict(observations), ensure_ascii=False) + caplog.text + repr(verdict)
    assert all(content not in visible for content in CONTENTS)
    assert "header.payload.signature" not in visible
    assert all("header.payload.signature" not in r.user_payload_json for r in model.requests)
    assert all(client.is_closed for client in clients.clients)
