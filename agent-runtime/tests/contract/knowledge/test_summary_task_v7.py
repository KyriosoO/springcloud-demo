from dataclasses import asdict, replace
import json

import pytest

from agent_runtime.knowledge.contracts import KnowledgeQuestionKind
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator
from agent_runtime.knowledge.evidence.summary_task_v6 import KnowledgeSummaryTaskV6, SUMMARY_PROMPT_V6
from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7, SUMMARY_PROMPT_V7
from tests.contract.knowledge.test_summary_task_v5 import _response
from tests.contract.knowledge.test_summary_task_v6 import (
    test_bad_input_rejected_before_transport, test_exact_decoder_rejects_invalid_shapes,
    test_duplicate_keys_and_markdown_rejected, test_nonstop_or_missing_output_rejected,
)
from tests.requirement_evidence_helpers import requirement_input, bound_input, output_for


@pytest.fixture(autouse=True)
def v7_contract_matrix(monkeypatch):
    # Run the same strict cases on V7, not copies with relaxed assertions.
    from tests.contract.knowledge import test_summary_task_v6 as old_tests
    monkeypatch.setattr(old_tests, "KnowledgeSummaryTaskV6", KnowledgeSummaryTaskV7)


def test_only_prompt_and_version_change_and_no_online_gold():
    _, _, value = bound_input()
    old, new = KnowledgeSummaryTaskV6.definition(), KnowledgeSummaryTaskV7.definition()
    assert replace(new, task_version="6", build_request=old.build_request) == old
    assert new.parse_response is old.parse_response
    assert replace(new.build_request(value), task_version="6", system_instruction=SUMMARY_PROMPT_V6) == old.build_request(value)
    assert new.task_version == new.build_request(value).task_version == "7"
    assert SUMMARY_PROMPT_V7.startswith(SUMMARY_PROMPT_V6)
    assert len(SUMMARY_PROMPT_V7.encode()) <= 8192
    for value in ("酒店", "住宿", "生活服务", "gold", "KB-", "chunk-", "015a"):
        assert value not in SUMMARY_PROMPT_V7
    for value in ("完整性优先", "同一个requirement", "不机械增加第二个引用", "用户", "归属", "insufficient_evidence"):
        assert value in SUMMARY_PROMPT_V7


@pytest.mark.parametrize("one_source", [True, False])
def test_single_or_joint_sources_can_prove_one_requirement_through_unchanged_validators(one_source):
    source = requirement_input(count=1 if one_source else 2, merged=True)
    source = replace(source, question_kind=KnowledgeQuestionKind.LOOKUP, evidence_requirements=source.evidence_requirements[:1],
        batch=replace(source.batch, candidates=tuple(replace(c, requirement_ids=("r1",) if i == 0 else ())
                                                    for i, c in enumerate(source.batch.candidates))))
    # Fictional taxonomy: no production case, tax fact or gold identifier.
    texts = (("丁类包含戊；戊是收集样本的活动。",) if one_source else
             ("戊是收集样本的活动。", "丁类包含戊。"))
    from tests.retrieval_helpers import candidate
    source = replace(source, batch=replace(source.batch, candidates=tuple(
        replace(c, candidate=candidate(chunk=f"c{i}", rank=i, content=text))
        for i, (c, text) in enumerate(zip(source.batch.candidates, texts, strict=True), 1))))
    source, bundle, value = bound_input(source)
    raw = asdict(output_for(value, merged=True))
    raw["points"] = [{"evidence_ref": e.evidence_ref, "quote": e.content} for e in value.evidence]
    raw["coverage"] = [{"requirement_id": "r1", "evidence_refs": [e.evidence_ref for e in value.evidence]}]
    output = KnowledgeSummaryTaskV7.definition().parse_response(_response(json.dumps(raw)))
    checked = RequirementCoverageValidator().validate(output=output, requirements=source.evidence_requirements,
                                                       summary_input=value, bundle=bundle)
    result = ExtractiveSummaryValidator().validate(output=checked, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())
    assert not result.insufficient and len(result.domain_result["points"]) == len(texts)


def test_definition_only_is_not_semantically_proven_by_a_structural_validator():
    # Existing finite validator cannot infer entailment. V7 must instruct refusal;
    # actual semantic compliance remains the original live UAT's responsibility.
    from tests.unit.knowledge.evidence.test_requirement_coverage import (
        test_semantic_counterexample_is_not_falsely_claimed_detectable_by_local_coverage,
    )
    test_semantic_counterexample_is_not_falsely_claimed_detectable_by_local_coverage()
    assert "仅找到定义而没有归属的直接证据时返回insufficient_evidence" in SUMMARY_PROMPT_V7
