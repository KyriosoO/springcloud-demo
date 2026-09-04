from __future__ import annotations

from dataclasses import replace
import json

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3, KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v4 import INSTRUCTION as V4_INSTRUCTION, KnowledgeRewriteTaskV4
from agent_runtime.knowledge.rewrite_v5 import DOMAIN_INSTRUCTION, INSTRUCTION, KnowledgeRewriteTaskV5
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v4 import _VALID


def test_v5_preserves_v4_clarification_and_shared_decoder_limits():
    previous, current = KnowledgeRewriteTaskV4.definition(), KnowledgeRewriteTaskV5.definition()
    value = KnowledgeSemanticPlanInput(minimized_question="税务政策定义", enabled_domain_ids=("tax.policy",))
    old_request, new_request = previous.build_request(value), current.build_request(value)
    assert current.task_version == new_request.task_version == "5"
    assert replace(current, task_version="4", build_request=previous.build_request) == previous
    assert replace(new_request, task_version="4", system_instruction=V4_INSTRUCTION) == old_request
    assert current.parse_response is KnowledgeRewriteTaskV3.definition().parse_response
    assert (current.max_input_bytes, current.max_output_tokens, current.timeout_ms) == (16384, 512, 8000)
    assert INSTRUCTION == V4_INSTRUCTION + DOMAIN_INSTRUCTION
    assert 0 < len(INSTRUCTION.encode("utf-8")) <= 8192
    for rule in ("只选tax.policy", "只选tax.law", "不可替代的依据", "不静默替换域", "不能按某个词"):
        assert rule in DOMAIN_INSTRUCTION
    for forbidden in ("酒店", "住宿", "UAT-KB", "chunk-", "gold", "2026"):
        assert forbidden not in INSTRUCTION


@pytest.mark.parametrize("value", _VALID)
def test_same_valid_wire_shapes_remain_accepted(value):
    response = _response(json.dumps(value))
    assert KnowledgeRewriteTaskV5.definition().parse_response(response) == KnowledgeRewriteTaskV4.definition().parse_response(response)


@pytest.mark.parametrize("raw", [
    "null", "[]", "{}", "{} {}", "not json",
    '{"outcome":"unsupported","outcome":"search","queries":[],"missing_conditions":[]}',
    json.dumps({**_VALID[0], "reason": "model_domain_justification"}),
    json.dumps({**_VALID[0], "queries": []}),
    json.dumps({**_VALID[0], "queries": _VALID[0]["queries"] * 2}),
    json.dumps({**_VALID[0], "queries": [{"domain_id": "other", "query": "税务政策"}]}),
    json.dumps({**_VALID[0], "missing_conditions": ["subject"]}),
    json.dumps({**_VALID[2], "missing_conditions": []}),
    json.dumps({**_VALID[2], "missing_conditions": ["intent"]}),
    json.dumps({**_VALID[2], "missing_conditions": ["subject", "subject"]}),
    json.dumps({**_VALID[2], "queries": _VALID[0]["queries"]}),
    json.dumps({**_VALID[3], "queries": _VALID[0]["queries"]}),
])
def test_v5_does_not_relax_decoder(raw):
    for task in (KnowledgeRewriteTaskV3, KnowledgeRewriteTaskV4, KnowledgeRewriteTaskV5):
        with pytest.raises(InvalidModelOutput):
            task.definition().parse_response(_response(raw))


@pytest.mark.parametrize("finish", [StructuredFinishKind.TOOL_CALLS])
def test_non_stop_fails_closed(finish):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV5.definition().parse_response(replace(_response(json.dumps(_VALID[0])), finish_kind=finish))


@pytest.mark.parametrize("question,domains", [("", ("tax.policy",)), ("税务政策", ()),
    ("税务政策", ("employee",)), ("税务政策", ("tax.policy", "tax.policy")), ("a" * 4097, ("tax.policy",))])
def test_input_validation_is_unchanged(question, domains):
    with pytest.raises(ValueError, match="invalid_plan_input"):
        KnowledgeRewriteTaskV5.definition().build_request(KnowledgeSemanticPlanInput(
            minimized_question=question, enabled_domain_ids=domains))
