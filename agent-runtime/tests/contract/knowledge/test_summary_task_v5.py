from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from agent_runtime.knowledge.evidence.contracts import SummaryEvidenceInput, SummaryOutcome
from agent_runtime.knowledge.evidence.summary_task_v4 import SUMMARY_PROMPT_V4, KnowledgeSummaryTaskV4
from agent_runtime.knowledge.evidence.summary_task_v5 import SUMMARY_PROMPT_V5, KnowledgeSummaryTaskV5
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse
from tests.contract.knowledge.test_summary_task_v4 import HISTORICAL_HASHES, ROOT, _input


def _response(content):
    return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content=content,
                                   tool_calls=(), usage_total_tokens=None)


def test_v5_only_changes_version_and_classification_instruction():
    old = KnowledgeSummaryTaskV4.definition()
    new = KnowledgeSummaryTaskV5.definition()
    assert replace(new, task_version=old.task_version, build_request=old.build_request) == old
    before, after = old.build_request(_input()), new.build_request(_input())
    assert replace(after, task_version=before.task_version,
                   system_instruction=before.system_instruction) == before
    assert after.task_version == "5"
    assert after.system_instruction == SUMMARY_PROMPT_V5
    assert SUMMARY_PROMPT_V5.startswith(SUMMARY_PROMPT_V4)
    assert len(SUMMARY_PROMPT_V5.encode()) <= 8192
    # Task envelope and serialized evidence payload have separate existing bounds.
    assert new.max_input_bytes == 49152 and new.max_output_tokens == 1536
    assert after.tools == ()
    payload = json.loads(after.user_payload_json)
    assert payload["question"] == _input().question
    assert all(set(item) == {"evidence_ref", "content", "domain_ids"} for item in payload["evidence"])


def test_v5_explains_proof_without_domain_specific_rules_or_forced_two_quotes():
    for text in ("与答案相关的显式分类上下文", "不能把用户给定的类别归属直接当作已证事实",
                 "不能只摘孤立关键词", "不展开与答案无关", "一段连续原文同时证明全部要点",
                 "不得为了凑双引用", "证据冲突", "最多5点", "每点最多512字符",
                 "同一ref内不连续", "检索coverage完整不表示答案已完整证明"):
        assert text in SUMMARY_PROMPT_V5
    for text in ("酒店", "住宿", "生活服务", "KB-", "gold", "candidate-"):
        assert text not in SUMMARY_PROMPT_V5


@pytest.mark.parametrize("count", [0, 9])
def test_v5_preserves_evidence_count_boundary(count):
    evidence = tuple(SummaryEvidenceInput(evidence_ref=f"e{i}", content="合成证据")
                     for i in range(1, count + 1))
    with pytest.raises(ValueError, match="knowledge.summary_input_invalid"):
        KnowledgeSummaryTaskV5.definition().build_request(replace(_input(), evidence=evidence))


def test_v5_preserves_input_byte_boundary():
    evidence = (SummaryEvidenceInput(evidence_ref="e1", content="字" * 12000),)
    with pytest.raises(ValueError, match="knowledge.summary_input_invalid"):
        KnowledgeSummaryTaskV5.definition().build_request(replace(_input(), evidence=evidence))


@pytest.mark.parametrize("content", [
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"合成证据"}]}',
    '{"outcome":"insufficient_evidence","points":[]}',
])
def test_v5_reuses_exact_v4_output_contract(content):
    new = KnowledgeSummaryTaskV5.definition().parse_response(_response(content))
    assert new == KnowledgeSummaryTaskV4.definition().parse_response(_response(content))
    assert new.outcome in {SummaryOutcome.ANSWER, SummaryOutcome.INSUFFICIENT_EVIDENCE}


@pytest.mark.parametrize("content", [
    '{"outcome":"answer","points":[],"classification":"invented"}',
    '{"outcome":"answer","outcome":"answer","points":[]}',
    '```json\n{"outcome":"insufficient_evidence","points":[]}\n```',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"合成证据","extra":1}]}',
    '{"outcome":"insufficient_evidence","points":[{"evidence_ref":"e1","quote":"合成证据"}]}',
])
def test_v5_rejects_invalid_shapes_without_parser_relaxation(content):
    with pytest.raises(InvalidModelOutput):
        KnowledgeSummaryTaskV5.definition().parse_response(_response(content))


def test_v1_to_v4_and_integrity_validator_remain_byte_identical():
    expected = dict(HISTORICAL_HASHES)
    expected[ROOT / "src/agent_runtime/knowledge/evidence/summary_task_v4.py"] = (
        "4536806fb8f23762e531c54c7061205a912994d0ad45e0997554815097bbd50e"
    )
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in expected} == expected
