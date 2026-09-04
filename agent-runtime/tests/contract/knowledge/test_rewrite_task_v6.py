from __future__ import annotations

from dataclasses import replace
import importlib
import json

import pytest

from agent_runtime.knowledge import rewrite_v5
from agent_runtime.knowledge import rewrite_v6
from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3, KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v5 import KnowledgeRewriteTaskV5
from agent_runtime.knowledge.rewrite_v6 import FOCUS_INSTRUCTION, INSTRUCTION, KnowledgeRewriteTaskV6
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v4 import _VALID


def test_v6_replaces_only_one_context_instruction_and_preserves_contract():
    previous, current = KnowledgeRewriteTaskV5.definition(), KnowledgeRewriteTaskV6.definition()
    value = KnowledgeSemanticPlanInput(minimized_question="税务政策定义", enabled_domain_ids=("tax.policy",))
    before, after = previous.build_request(value), current.build_request(value)
    assert current.task_version == after.task_version == "6"
    assert replace(current, task_version="5", build_request=previous.build_request) == previous
    assert replace(after, task_version="5", system_instruction=before.system_instruction) == before
    assert current.parse_response is KnowledgeRewriteTaskV3.definition().parse_response
    assert (current.max_input_bytes, current.max_output_tokens, current.timeout_ms) == (16384, 512, 8000)
    old = rewrite_v6._CONTEXT_INSTRUCTION_V5
    assert before.system_instruction.count(old) == 1
    assert old not in INSTRUCTION and INSTRUCTION.count(FOCUS_INSTRUCTION) == 1
    assert INSTRUCTION.replace(FOCUS_INSTRUCTION, old, 1) == before.system_instruction
    assert 0 < len(INSTRUCTION.encode("utf-8")) <= 8192
    for rule in ("本域待证明的子问题", "不能借聚焦删除或替换", "不得遗漏任何子问题", "不得为普通问题伪造税务意图"):
        assert rule in FOCUS_INSTRUCTION
    for forbidden in ("酒店", "住宿", "UAT-KB", "chunk-", "gold", "2026"):
        assert forbidden not in INSTRUCTION


@pytest.mark.parametrize("occurrences", [0, 2])
def test_source_instruction_drift_fails_closed(monkeypatch, occurrences):
    old = rewrite_v6._CONTEXT_INSTRUCTION_V5
    try:
        with monkeypatch.context() as patch:
            patch.setattr(rewrite_v5, "INSTRUCTION", old * occurrences)
            with pytest.raises(ValueError, match="rewrite_v6_source_instruction_invalid"):
                importlib.reload(rewrite_v6)
    finally:
        importlib.reload(rewrite_v6)


@pytest.mark.parametrize("value", _VALID)
def test_v6_reuses_exact_valid_wire_shapes(value):
    response = _response(json.dumps(value))
    assert KnowledgeRewriteTaskV6.definition().parse_response(response) == KnowledgeRewriteTaskV5.definition().parse_response(response)


@pytest.mark.parametrize("raw", [
    "null", "[]", "{}", "{} {}", "not json",
    '{"outcome":"unsupported","outcome":"search","queries":[],"missing_conditions":[]}',
    '{"outcome":"unsupported","queries":[],"missing_conditions":NaN}',
    json.dumps({**_VALID[0], "subquestions": ["new field"]}),
    json.dumps({**_VALID[0], "queries": []}),
    json.dumps({**_VALID[0], "queries": _VALID[0]["queries"] * 2}),
    json.dumps({**_VALID[0], "queries": [{"domain_id": "other", "query": "税务政策"}]}),
    json.dumps({**_VALID[0], "queries": [{"domain_id": "tax.policy", "query": "a" * 1025}]}),
    json.dumps({**_VALID[0], "queries": [{"domain_id": "tax.policy", "query": "税务\n政策"}]}),
    json.dumps({**_VALID[0], "missing_conditions": ["subject"]}),
    json.dumps({**_VALID[2], "missing_conditions": []}),
    json.dumps({**_VALID[2], "missing_conditions": ["intent"]}),
    json.dumps({**_VALID[2], "missing_conditions": ["subject", "subject"]}),
    json.dumps({**_VALID[2], "queries": _VALID[0]["queries"]}),
    json.dumps({**_VALID[3], "queries": _VALID[0]["queries"]}),
])
def test_v6_does_not_relax_decoder(raw):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV6.definition().parse_response(_response(raw))


def test_non_stop_fails_closed():
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV6.definition().parse_response(replace(
            _response(json.dumps(_VALID[0])), finish_kind=StructuredFinishKind.TOOL_CALLS))


@pytest.mark.parametrize("question,domains", [("", ("tax.policy",)), ("税务政策", ()),
    ("税务政策", ("employee",)), ("税务政策", ("tax.policy", "tax.policy")), ("a" * 4097, ("tax.policy",))])
def test_input_validation_is_unchanged(question, domains):
    with pytest.raises(ValueError, match="invalid_plan_input"):
        KnowledgeRewriteTaskV6.definition().build_request(KnowledgeSemanticPlanInput(
            minimized_question=question, enabled_domain_ids=domains))
