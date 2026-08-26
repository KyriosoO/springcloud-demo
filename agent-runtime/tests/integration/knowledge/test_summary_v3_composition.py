from __future__ import annotations

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2


def test_production_composition_registers_only_summary_v3() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)

    assert tasks is not None
    assert tasks.rewrite.task_version == "1"
    assert tasks.summary.task_version == "3"
    assert tasks.summary.task_id is KnowledgeSummaryTaskV2.definition().task_id


def test_disabled_composition_creates_no_task_definitions() -> None:
    assert KnowledgeCompositionRoot.task_definitions(enabled=False) is None
