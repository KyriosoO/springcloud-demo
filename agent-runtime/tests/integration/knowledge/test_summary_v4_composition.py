from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.evidence.summary_task_v3 import KnowledgeSummaryTaskV3
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2
from agent_runtime.knowledge.evidence.summary_task_v4 import KnowledgeSummaryTaskV4
from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3
from agent_runtime.knowledge.rewrite_v4 import KnowledgeRewriteTaskV4
from agent_runtime.knowledge.rewrite_v5 import KnowledgeRewriteTaskV5
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_production_composition_registers_only_current_summary_v5() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)

    assert tasks is not None
    assert tasks.rewrite.task_version == "6"
    assert tasks.summary.task_version == "5"
    assert tasks.summary.task_id is KnowledgeSummaryTaskV3.definition().task_id


def test_disabled_composition_creates_no_task_definitions() -> None:
    assert KnowledgeCompositionRoot.task_definitions(enabled=False) is None


@pytest.mark.parametrize("old_task", [KnowledgeSummaryTaskV1, KnowledgeSummaryTaskV2,
                                      KnowledgeSummaryTaskV3, KnowledgeSummaryTaskV4])
def test_current_root_rejects_old_summary_before_model_use(old_task) -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    with pytest.raises(ValueError, match="knowledge.production_task_version_invalid"):
        KnowledgeCompositionRoot.build_provider(
            settings=KnowledgeSettings.from_env({
                "AGENT_KNOWLEDGE_ENABLED": "true",
                "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
            }),
            model=None,  # type: ignore[arg-type]
            tasks=replace(tasks, summary=old_task.definition()),
            retrieval=object(),
        )


@pytest.mark.parametrize("old_task", [KnowledgeRewriteTaskV3, KnowledgeRewriteTaskV4, KnowledgeRewriteTaskV5])
def test_current_production_root_rejects_old_rewrite_v3_before_model_use(old_task) -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    with pytest.raises(ValueError, match="knowledge.production_task_version_invalid"):
        KnowledgeCompositionRoot.build_provider(
            settings=KnowledgeSettings.from_env({
                "AGENT_KNOWLEDGE_ENABLED": "true",
                "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
            }),
            model=None,  # type: ignore[arg-type]
            tasks=replace(tasks, rewrite=old_task.definition()),
            retrieval=object(),
        )
