from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v7 import KnowledgeRewriteTaskV7
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.contracts import InvalidModelOutput
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v7 import invalid_values, wire_plan


def test_v9_reuses_exact_decoder_and_only_changes_instruction_and_version() -> None:
    old = KnowledgeRewriteTaskV8.definition()
    new = KnowledgeRewriteTaskV9.definition()
    assert new.parse_response is old.parse_response is KnowledgeRewriteTaskV7.definition().parse_response
    assert replace(new, task_version=old.task_version, build_request=old.build_request) == old
    value = KnowledgeSemanticPlanInput(minimized_question="政策及法律规则", enabled_domain_ids=("tax.policy", "tax.law"))
    previous, request = old.build_request(value), new.build_request(value)
    assert replace(request, task_version=previous.task_version, system_instruction=previous.system_instruction) == previous
    assert request.task_version == "9"
    assert request.max_output_tokens == 1536
    assert len(request.system_instruction.encode("utf-8")) <= 8192
    assert "先判断用户是在要求适用结论" in request.system_instruction
    assert "每个query保留原问题显式" not in request.system_instruction
    assert "每个query保留完整比例及税率主题" not in request.system_instruction
    assert "未分配给任何focus" in request.system_instruction
    assert "每个受影响域至少一个focus" in request.system_instruction
    assert "不能用去重掩盖遗漏" in request.system_instruction
    assert "否则unsupported" in request.system_instruction
    assert not any(term in request.system_instruction for term in ("酒店", "KRB-", "gold", "财税〔2011〕100号"))


@pytest.mark.parametrize("change", ["missing", "duplicated"])
def test_instruction_drift_fails_closed(monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    definition = KnowledgeRewriteTaskV8.definition()
    original_builder = definition.build_request

    def changed(value: KnowledgeSemanticPlanInput):
        request = original_builder(value)
        text = request.system_instruction
        from agent_runtime.knowledge.rewrite_v9 import _PREVIOUS_CONSTRAINTS
        text = text.replace(_PREVIOUS_CONSTRAINTS, "" if change == "missing" else _PREVIOUS_CONSTRAINTS * 2)
        return replace(request, system_instruction=text)

    monkeypatch.setattr(KnowledgeRewriteTaskV8, "definition", staticmethod(lambda: replace(definition, build_request=changed)))
    with pytest.raises(ValueError, match="instruction_baseline_invalid"):
        KnowledgeRewriteTaskV9.definition().build_request(KnowledgeSemanticPlanInput(
            minimized_question="税务规则", enabled_domain_ids=("tax.policy",),
        ))


@pytest.mark.parametrize("value", invalid_values())
def test_same_exact_invalid_wire_matrix(value) -> None:
    import json
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(value)))


@pytest.mark.parametrize("value", [
    wire_plan(), wire_plan(applicability=True), wire_plan(applicability=True, second_domain=True),
    dict(outcome="clarification_required", question_kind="none", queries=[], requirements=[], missing_conditions=["taxpayer_type"]),
    dict(outcome="unsupported", question_kind="none", queries=[], requirements=[], missing_conditions=[]),
])
def test_same_exact_valid_wire_matrix(value) -> None:
    import json
    response = _response(json.dumps(value))
    assert KnowledgeRewriteTaskV9.definition().parse_response(response) == KnowledgeRewriteTaskV7.definition().parse_response(response)


def test_old_tasks_and_guards_keep_the_prechange_git_source() -> None:
    repo = Path(__file__).resolve().parents[4]
    head = "fbf47cff1a0fbc038a6d7e25c65fe0e666bcf3f6"
    for name in ("rewrite_v7.py", "rewrite_v8.py", "question_semantics.py", "tax_question_semantics.py",
                 "document_reference_semantics.py", "evidence_requirements.py"):
        relative = f"agent-runtime/src/agent_runtime/knowledge/{name}"
        frozen = subprocess.check_output(["git", "show", f"{head}:{relative}"], cwd=repo)
        assert (repo / relative).read_text(encoding="utf-8").encode() == frozen
