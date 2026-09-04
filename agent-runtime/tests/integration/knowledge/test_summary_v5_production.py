"""Synthetic responses verify wiring/integrity, not a real model's semantic coverage."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, replace

import pytest

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import (
    _KnowledgeClientFactory, _KnowledgeModelTransport, _enabled_environment,
)


QUESTION = "税务测试资料中，甲类中的乙项如何定义？"
CLASSIFICATION = "合成测试分类：甲类包括乙项和丙项。"
DEFINITION = "合成测试定义：乙项是提供丁种支持的活动。"


class _Clients(_KnowledgeClientFactory):
    def __init__(self, case):
        super().__init__()
        self.case = case

    def _search_result(self, request):
        result = super()._search_result(request)
        contents = [DEFINITION, CLASSIFICATION, "合成测试资料：丙项另行规定。"]
        if self.case == "single_quote":
            contents[0] = CLASSIFICATION + DEFINITION
        elif self.case == "missing":
            contents[1] = "合成测试资料：没有给出乙项的分类。"
        elif self.case == "conflict":
            contents[2] = "合成测试分类：乙项不属于甲类。"
        for item, content in zip(result["candidates"], contents, strict=True):
            item["content"] = content
            item["contentSha256"] = hashlib.sha256(content.encode()).hexdigest()
        return result


class _Model(_KnowledgeModelTransport):
    def __init__(self, case):
        super().__init__()
        self.case = case

    async def complete(self, request, *, call_deadline):
        response = await super().complete(request, call_deadline=call_deadline)
        if request.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY:
            return response
        assert request.task_version == "5"
        if self.case == "timeout":
            raise TimeoutError("synthetic timeout")
        if self.case == "model_failure":
            raise RuntimeError("synthetic model failure")
        if self.case == "cancel":
            raise asyncio.CancelledError()
        payload = json.loads(request.user_payload_json)
        evidence = payload["evidence"]
        points = [{"evidence_ref": item["evidence_ref"], "quote": item["content"]}
                  for item in evidence[:2]]
        if self.case == "single_quote":
            points = points[:1]
        elif self.case == "unknown_ref":
            points[0]["evidence_ref"] = "e8"
        elif self.case == "duplicate_ref":
            points[1] = points[0]
        elif self.case == "non_substring":
            points[0]["quote"] = "合成测试定义：" + "不存在的拼接内容"
        elif self.case == "oversized_quote":
            points[0]["quote"] = "字" * 513
        content = {"outcome": "answer", "points": points}
        if self.case in {"missing", "conflict"}:
            content = {"outcome": "insufficient_evidence", "points": []}
        elif self.case == "extra_field":
            content["classification"] = "must-not-pass"
        return replace(response, content=json.dumps(content, ensure_ascii=False))


@pytest.mark.parametrize("case, expected", [
    ("two_quotes", CapabilityStatus.SUCCESS),
    ("single_quote", CapabilityStatus.SUCCESS),
    ("missing", CapabilityStatus.NO_RESULT),
    ("conflict", CapabilityStatus.NO_RESULT),
    ("unknown_ref", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("duplicate_ref", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("non_substring", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("oversized_quote", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("extra_field", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("model_failure", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("timeout", CapabilityStatus.TIMEOUT),
    ("cancel", None),
])
@pytest.mark.asyncio
async def test_current_runtime_summary_v5_proof_contract_and_failure_boundaries(case, expected, caplog, monkeypatch):
    business_calls = 0

    async def reject_business(self, outbound):
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("No Business outbound in Knowledge tests")

    monkeypatch.setattr(HttpxBusinessDomainTransport, "send", reject_business)
    model, clients = _Model(case), _Clients(case)
    runtime = build_runtime(_enabled_environment(), model_transport=model,
                            knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            if case == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
            else:
                outcome = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
                assert outcome.status is expected, outcome.failure
                assert outcome.capability_id == "knowledge.query"
                if expected is CapabilityStatus.SUCCESS:
                    assert len(outcome.user_result["points"]) == (1 if case == "single_quote" else 2)
                    assert [point["quote"] for point in outcome.user_result["points"]] == (
                        [CLASSIFICATION + DEFINITION] if case == "single_quote"
                        else [DEFINITION, CLASSIFICATION]
                    )
                elif expected is CapabilityStatus.NO_RESULT:
                    assert dict(outcome.user_result) == {"reason": "insufficient_evidence"}
                else:
                    assert outcome.user_result is None
            observations = collector.snapshot()
    finally:
        await runtime.aclose()
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
        (ModelTaskId.KNOWLEDGE_REWRITE, "6"), (ModelTaskId.KNOWLEDGE_SUMMARY, "5"),
    ]
    payload = json.loads(model.requests[-1].user_payload_json)
    assert business_calls == 0
    assert all("header.payload.signature" not in request.user_payload_json for request in model.requests)
    assert payload["question"] == QUESTION
    assert len(payload["evidence"]) == 3
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/embed") == clients.paths.count("/rerank") == 1
    assert set(clients.paths) == {"/es/knowledge/search", "/embed", "/rerank"}
    assert clients.es_authorizations == ["Bearer header.payload.signature"] * 2
    visible = json.dumps(asdict(observations), ensure_ascii=False) + caplog.text
    assert "header.payload.signature" not in visible
    assert DEFINITION not in visible and CLASSIFICATION not in visible
    assert all(client.is_closed for client in clients.clients)
