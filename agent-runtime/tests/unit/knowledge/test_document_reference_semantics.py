"""DR-KFLOW-027: lexical boundaries, not unrestricted semantic equivalence."""
from dataclasses import asdict, FrozenInstanceError
import hashlib
from pathlib import Path
import subprocess

import pytest

from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement, KnowledgeRequirementKind
from agent_runtime.knowledge.document_reference_semantics import DocumentReferenceSemanticGuard
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.evidence_requirements import validate_requirement_focuses
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.tax_question_semantics import TaxQuestionSemanticGuard


REFERENCE = "财税〔2011〕100号"


def accepts(original, candidate):
    guard = DocumentReferenceSemanticGuard()
    return guard.validate_candidate(candidate=candidate, constraints=guard.extract(original), max_chars=1024).accepted


@pytest.mark.parametrize("prefix", [
    "请分别查找", "请帮我查询", "帮我同时检索", "麻烦查阅", "麻烦帮我查看",
    "请对比", "分别比较", "查询", "检索", "查阅", "查看", "对比", "比较", "",
])
@pytest.mark.parametrize("reference", [REFERENCE, "国税函[2009]625号", "苏财税〔2025〕008号"])
def test_request_prefix_only_is_removed(prefix, reference):
    text = prefix + reference + "的税务规定"
    assert DocumentReferenceSemanticGuard().extract(text).document_numbers == (reference,)
    assert accepts(text, reference + "的税务规定")


@pytest.mark.parametrize("text", [
    "请不要查找" + REFERENCE, "依据" + REFERENCE, "苏" + REFERENCE,
    "查询〔2011〕100号", "请查找税务_发〔2011〕100号", "请查找财税（2011）100号",
    "请查找财税〔２０１１〕100号", "财政部公告2023年第6号",
])
def test_unknown_or_ambiguous_forms_keep_legacy_token(text):
    assert DocumentReferenceSemanticGuard().extract(text) == TaxQuestionSemanticGuard().extract(text)


@pytest.mark.parametrize("candidate", [
    "国税函〔2011〕100号", "财税〔2012〕100号", "财税〔2011〕101号", "财税[2011]100号",
    "财税〔2011〕0100号", "财税", "〔2011〕100号", "苏财税〔2011〕100号",
    REFERENCE + "，" + REFERENCE,
])
def test_document_identity_and_multiplicity_are_not_relaxed(candidate):
    assert not accepts("请分别查找" + REFERENCE, candidate)


def test_regional_issuer_is_not_discarded_and_prefix_is_not_recursive():
    assert not accepts("请查询苏财税〔2025〕8号", "财税〔2025〕8号")
    assert not accepts("查询查询" + REFERENCE, REFERENCE)
    assert DocumentReferenceSemanticGuard().extract("查询查询" + REFERENCE).document_numbers == ("查询" + REFERENCE,)


def test_only_document_group_changes_and_constraints_remain_immutable():
    text = "请查找" + REFERENCE + "，一般纳税人2026年1月1日不得按6%适用第十条"
    old = asdict(TaxQuestionSemanticGuard().extract(text))
    constraints = DocumentReferenceSemanticGuard().extract(text)
    new = asdict(constraints)
    assert old.pop("document_numbers") == ("请查找" + REFERENCE,)
    assert new.pop("document_numbers") == (REFERENCE,)
    assert new == old
    for before, after in [("2026", "2027"), ("6%", "9%"), ("不得", ""), ("第十条", "第十一条")]:
        assert not accepts(text, text.replace("请查找", "").replace(before, after))
    with pytest.raises(FrozenInstanceError):
        constraints.document_numbers = ()


@pytest.mark.parametrize("value", [None, 1, "", "请查找" + REFERENCE + "\x00", "请查找" + REFERENCE + "\u200b", "一般计税 " * 33])
def test_original_validation_precedes_normalization(value):
    with pytest.raises(KnowledgeInputError):
        DocumentReferenceSemanticGuard().extract(value)


def test_length_and_legacy_behaviour():
    text = "请分别查找" + REFERENCE
    assert not accepts(text, REFERENCE + "甲" * 1024)
    for old in (QuestionSemanticGuard(), TaxQuestionSemanticGuard()):
        assert old.extract(text).document_numbers == (text,)
        assert not old.validate_candidate(candidate=REFERENCE, constraints=old.extract(text), max_chars=1024).accepted


def test_same_guard_for_query_and_focus_preserves_counter_subset():
    original = "请分别查找财税〔2011〕100号的软件产品定义，以及增值税法第十条的销售服务税率规定。"
    guard = DocumentReferenceSemanticGuard()
    for focus in ("财税〔2011〕100号的软件产品定义", "增值税法第十条的销售服务税率规定"):
        requirement = KnowledgeEvidenceRequirement(requirement_id="r1", domain_id="tax.policy", kind=KnowledgeRequirementKind.RULE, focus=focus)
        validate_requirement_focuses(original_question=original, requirements=(requirement,), semantic_guard=guard)
    for focus in ("国税函〔2011〕100号的软件产品定义", REFERENCE + "，" + REFERENCE, "财税〔2012〕100号"):
        requirement = KnowledgeEvidenceRequirement(requirement_id="r1", domain_id="tax.policy", kind=KnowledgeRequirementKind.RULE, focus=focus)
        with pytest.raises(KnowledgeInputError, match="knowledge.requirement_focus_introduced_constraint"):
            validate_requirement_focuses(original_question=original, requirements=(requirement,), semantic_guard=guard)


def test_frozen_guard_source_blobs_are_unchanged():
    root = Path(__file__).resolve().parents[4]
    for name in ("question_semantics.py", "tax_question_semantics.py"):
        relative = f"agent-runtime/src/agent_runtime/knowledge/{name}"
        original = subprocess.check_output(["git", "show", f"fbc0179a847bafaf044967afd8832013ca251ae2:{relative}"], cwd=root)
        # Git checkout may use CRLF; comparison preserves all source semantics.
        current = (root / relative).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(current).digest() == hashlib.sha256(original.replace(b"\r\n", b"\n")).digest()
