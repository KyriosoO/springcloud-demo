from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.evidence.summary_task_v3 import KnowledgeSummaryTaskV3
from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_production_composition_registers_only_summary_v4() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)

    assert tasks is not None
    assert tasks.rewrite.task_version == "4"
    assert tasks.summary.task_version == "4"
    assert tasks.summary.task_id is KnowledgeSummaryTaskV3.definition().task_id


def test_disabled_composition_creates_no_task_definitions() -> None:
    assert KnowledgeCompositionRoot.task_definitions(enabled=False) is None


def test_current_production_root_rejects_old_rewrite_v3_before_model_use() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    with pytest.raises(ValueError, match="knowledge.production_task_version_invalid"):
        KnowledgeCompositionRoot.build_provider(
            settings=KnowledgeSettings.from_env({
                "AGENT_KNOWLEDGE_ENABLED": "true",
                "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
            }),
            model=None,  # type: ignore[arg-type]
            tasks=replace(tasks, rewrite=KnowledgeRewriteTaskV3.definition()),
            retrieval=object(),
        )
