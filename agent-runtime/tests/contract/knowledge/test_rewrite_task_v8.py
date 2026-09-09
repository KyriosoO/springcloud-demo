"""Non-live instruction/contract checks, not proof of LLM intent accuracy."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V2, KNOWLEDGE_QUALITY_VERSION_V3
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v7 import KnowledgeRewriteTaskV7
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
from agent_runtime.model.contracts import InvalidModelOutput
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v7 import invalid_values, wire_plan


def input_value():
    return KnowledgeSemanticPlanInput(minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law"))


def test_only_version_and_intent_instruction_change():
    old, new = KnowledgeRewriteTaskV7.definition(), KnowledgeRewriteTaskV8.definition()
    before, after = old.build_request(input_value()), new.build_request(input_value())
    assert replace(new, task_version="7", build_request=old.build_request) == old
    assert replace(after, task_version="7", system_instruction=before.system_instruction) == before
    assert new.parse_response is old.parse_response
    assert (new.max_input_bytes, new.max_output_tokens, new.timeout_ms) == (16384, 1536, 8000)
    assert 0 < len(after.system_instruction.encode()) <= 8192
    # The removed paragraph must not continue competing with clarification-first.
    assert "确定条件下的具体适用判断" not in after.system_instruction
    for rule in (
        "先判断用户是在要求适用结论，还是查阅资料，再判断必要用户条件",
        "不要求出现具体企业或个人名称", "不得默认一般纳税人、一般计税、当前期间",
        "不得把条件不完整的适用判断改成lookup", "不得机械要求全部四类条件",
        "单独出现适用等词不决定意图", "不伪造缺失条件",
        "question_kind为none，queries和requirements为空", "只有允许search后才生成查询和证据需求",
        "applicability必须各有且仅有一个subject_scope、rule、temporal_scope",
    ):
        assert rule in after.system_instruction
    for forbidden in ("酒店", "住宿", "UAT-KB", "gold", "chunk-", "2026"):
        assert forbidden not in after.system_instruction
    assert after.system_instruction.count("澄清结构：") == 1
    assert after.system_instruction.count("不支持结构：") == 1


@pytest.mark.parametrize("repetitions", [0, 2])
def test_nonunique_baseline_paragraph_is_rejected(repetitions, monkeypatch):
    from agent_runtime.knowledge import rewrite_v8
    old = KnowledgeRewriteTaskV7.definition()
    request = old.build_request(input_value())
    broken = request.system_instruction.replace(rewrite_v8._PREVIOUS_INTENT, rewrite_v8._PREVIOUS_INTENT * repetitions)
    monkeypatch.setattr(KnowledgeRewriteTaskV7, "definition", staticmethod(lambda: replace(
        old, build_request=lambda value: replace(request, system_instruction=broken))))
    with pytest.raises(ValueError, match="instruction_baseline_invalid"):
        KnowledgeRewriteTaskV8.definition().build_request(input_value())


@pytest.mark.parametrize("value", invalid_values())
def test_all_v7_invalid_shapes_remain_invalid(value):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV8.definition().parse_response(_response(json.dumps(value)))


@pytest.mark.parametrize("value", [wire_plan(), wire_plan(applicability=True), wire_plan(applicability=True, second_domain=True),
    dict(outcome="clarification_required", question_kind="none", queries=[], requirements=[], missing_conditions=["taxpayer_type"]),
    dict(outcome="unsupported", question_kind="none", queries=[], requirements=[], missing_conditions=[])])
def test_valid_outputs_are_identical_to_v7(value):
    response = _response(json.dumps(value))
    assert KnowledgeRewriteTaskV8.definition().parse_response(response) == KnowledgeRewriteTaskV7.definition().parse_response(response)


@pytest.mark.parametrize("version", ["7", "unknown", "9"])
def test_current_root_rejects_old_or_invented_version(version):
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks.rewrite.task_version == "8" and tasks.summary.task_version == "7"
    with pytest.raises(ValueError, match="production_task_version_invalid"):
        KnowledgeCompositionRoot._validate_tasks(replace(tasks, rewrite=replace(tasks.rewrite, task_version=version)))


@pytest.mark.parametrize("quality,version,valid", [
    (KNOWLEDGE_QUALITY_VERSION_V3, "7", True), (KNOWLEDGE_QUALITY_VERSION_V3, "8", True),
    (KNOWLEDGE_QUALITY_VERSION_V3, "9", False), (KNOWLEDGE_QUALITY_VERSION_V2, "8", False),
])
def test_only_same_wire_versions_can_share_internal_requirement_contract(quality, version, valid):
    kwargs = dict(gateway=None, context=None, enabled_domain_ids=("tax.policy",), quality_version=quality,
                  definition=replace(KnowledgeRewriteTaskV8.definition(), task_version=version))
    if valid:
        KnowledgeSemanticPlanner(**kwargs)
    else:
        with pytest.raises(ValueError, match="requirement_version_mismatch"):
            KnowledgeSemanticPlanner(**kwargs)


def test_frozen_task_bytes_are_unchanged():
    repo = Path(__file__).resolve().parents[4]
    for name in ("rewrite_v4.py", "rewrite_v5.py", "rewrite_v6.py", "rewrite_v7.py"):
        relative = f"agent-runtime/src/agent_runtime/knowledge/{name}"
        frozen = subprocess.check_output(["git", "show", f"1fbd62aeebc01af0951ddcd62281be589f6eba6a:{relative}"], cwd=repo)
        # Git source uses LF; read working source with universal newlines.
        current = (repo / relative).read_text(encoding="utf-8").encode()
        assert hashlib.sha256(current).digest() == hashlib.sha256(frozen).digest()
