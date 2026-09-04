from __future__ import annotations

import json

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3, KnowledgeSemanticPlanInput
from agent_runtime.model.contracts import InvalidModelOutput
from tests.contract.knowledge.test_rewrite_task_v2 import _response


def search(query="住宿服务增值税政策", domain="tax.policy"):
    return {"outcome": "search", "queries": [{"domain_id": domain, "query": query}], "missing_conditions": []}


def test_v3_exposes_only_enabled_logical_domains_and_exact_shapes():
    task = KnowledgeRewriteTaskV3.definition()
    request = task.build_request(KnowledgeSemanticPlanInput(
        minimized_question="住宿服务增值税政策", enabled_domain_ids=("tax.policy",),
    ))
    assert task.task_version == "3"
    assert task.max_input_bytes == 16384 and task.max_output_tokens == 512
    assert json.loads(request.user_payload_json)["domains"] == [
        {"domain_id": "tax.policy", "description": "税收政策、公告、服务分类、优惠、征收管理及实施办法原文"}
    ]
    assert "不" in request.system_instruction and "clarification_required" in request.system_instruction


@pytest.mark.parametrize("value", [
    search(),
    {"outcome": "search", "queries": [search()["queries"][0], search(domain="tax.law")["queries"][0]], "missing_conditions": []},
    {"outcome": "clarification_required", "queries": [], "missing_conditions": ["taxpayer_type"]},
    {"outcome": "unsupported", "queries": [], "missing_conditions": []},
])
def test_v3_accepts_only_closed_outcome_shapes(value):
    result = KnowledgeRewriteTaskV3.definition().parse_response(_response(json.dumps(value)))
    assert result.outcome == value["outcome"]


@pytest.mark.parametrize("raw", [
    "null", "[]", "{}", '{"candidates":["税率"]}',
    json.dumps(search(query="")), json.dumps(search(query="x" * 1025)),
    json.dumps(search(query="税率\n")), json.dumps(search(domain="employee")),
    json.dumps(search(query=17)),
    '{"outcome":"unsupported","outcome":"search","queries":[],"missing_conditions":[]}',
    '{"outcome":"search","queries":[{"domain_id":"tax.policy","domain_id":"tax.law","query":"税率"}],"missing_conditions":[]}',
    json.dumps(search()) + " {}",
    json.dumps({**search(), "extra": 1}),
    json.dumps({**search(), "missing_conditions": ["subject"]}),
    json.dumps({**search(), "queries": []}),
    json.dumps({**search(), "queries": search()["queries"] * 2}),
    json.dumps({"outcome": "clarification_required", "queries": [], "missing_conditions": []}),
    json.dumps({"outcome": "clarification_required", "queries": [], "missing_conditions": ["date"]}),
    json.dumps({"outcome": "clarification_required", "queries": [], "missing_conditions": ["subject", "subject"]}),
    json.dumps({**search(), "outcome": "unsupported"}),
    '{"outcome":"unsupported","queries":[],"missing_conditions":NaN}',
])
def test_v3_rejects_invalid_json_or_invented_contract(raw):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV3.definition().parse_response(_response(raw))
