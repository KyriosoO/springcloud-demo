from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3, KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v4 import INSTRUCTION, KnowledgeRewriteTaskV4
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind
from tests.contract.knowledge.test_rewrite_task_v2 import _response


def test_v4_only_changes_prompt_and_version_not_shared_contract_or_budgets():
    v3, v4 = KnowledgeRewriteTaskV3.definition(), KnowledgeRewriteTaskV4.definition()
    value = KnowledgeSemanticPlanInput(minimized_question="住宿服务税务分类", enabled_domain_ids=("tax.policy",))
    original, current = v3.build_request(value), v4.build_request(value)
    assert v4.task_version == current.task_version == "4"
    assert replace(current, task_version=original.task_version, system_instruction=original.system_instruction) == original
    assert replace(v4, task_version=v3.task_version, build_request=v3.build_request) == v3
    assert v4.parse_response is v3.parse_response
    assert (v4.max_input_bytes, v4.max_output_tokens, v4.timeout_ms) == (16384, 512, 8000)
    assert 0 < len(INSTRUCTION.encode("utf-8")) <= 8192
    assert "具体主体作单一适用判断" in original.system_instruction
    assert "不要求出现具体企业或个人名称" in current.system_instruction
    assert "不得机械要求所有四类条件" in current.system_instruction
    assert "不伪造缺失条件" in current.system_instruction
    assert "酒店" not in current.system_instruction


_VALID = [
    {"outcome": "search", "queries": [{"domain_id": "tax.policy", "query": "增值税政策"}], "missing_conditions": []},
    {"outcome": "search", "queries": [{"domain_id": "tax.policy", "query": "增值税政策"},
                                      {"domain_id": "tax.law", "query": "增值税法"}], "missing_conditions": []},
    {"outcome": "clarification_required", "queries": [], "missing_conditions": ["taxpayer_type", "applicable_period"]},
    {"outcome": "unsupported", "queries": [], "missing_conditions": []},
]


@pytest.mark.parametrize("value", _VALID)
def test_v4_and_v3_decode_the_same_valid_output(value):
    response = _response(json.dumps(value))
    assert KnowledgeRewriteTaskV4.definition().parse_response(response) == KnowledgeRewriteTaskV3.definition().parse_response(response)


@pytest.mark.parametrize("task_type", [KnowledgeRewriteTaskV3, KnowledgeRewriteTaskV4])
@pytest.mark.parametrize("raw", [
    "null", "[]", "{}", json.dumps({**_VALID[0], "intent": "lookup"}),
    json.dumps({**_VALID[0], "queries": []}),
    json.dumps({**_VALID[0], "queries": _VALID[0]["queries"] * 2}),
    json.dumps({**_VALID[0], "missing_conditions": ["subject"]}),
    json.dumps({**_VALID[2], "missing_conditions": []}),
    json.dumps({**_VALID[2], "missing_conditions": ["intent"]}),
    json.dumps({**_VALID[2], "missing_conditions": ["subject", "subject"]}),
    json.dumps({**_VALID[2], "missing_conditions": ["subject", "taxpayer_type", "calculation_method", "applicable_period"]}),
    json.dumps({**_VALID[2], "queries": _VALID[0]["queries"]}),
    json.dumps({**_VALID[3], "queries": _VALID[0]["queries"]}),
    json.dumps(_VALID[0]) + " {}",
    '{"outcome":"unsupported","outcome":"search","queries":[],"missing_conditions":[]}',
    '{"outcome":"unsupported","queries":[],"missing_conditions":NaN}',
])
def test_v4_preserves_strict_output_rejections(task_type, raw):
    with pytest.raises(InvalidModelOutput):
        task_type.definition().parse_response(_response(raw))


def test_v4_rejects_non_stop_response():
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV4.definition().parse_response(replace(_response(json.dumps(_VALID[0])), finish_kind=StructuredFinishKind.TOOL_CALLS))


@pytest.mark.parametrize("question,domains", [("", ("tax.policy",)), ("税务政策", ()),
    ("税务政策", ("employee",)), ("税务政策", ("tax.policy", "tax.policy")), ("a" * 4097, ("tax.policy",))])
def test_v4_preserves_input_contract(question, domains):
    with pytest.raises(ValueError, match="invalid_plan_input"):
        KnowledgeRewriteTaskV4.definition().build_request(KnowledgeSemanticPlanInput(
            minimized_question=question, enabled_domain_ids=domains))
