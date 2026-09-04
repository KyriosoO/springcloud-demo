from __future__ import annotations

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_disabled_knowledge_registers_descriptor_without_tasks_stages_or_clients() -> None:
    settings = KnowledgeSettings.from_env({})
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=settings.enabled)
    provider = KnowledgeCompositionRoot.build_provider(
        settings=settings,
        model=None,  # type: ignore[arg-type]
        tasks=tasks,
        retrieval=None,
    )

    registration = provider.registrations()[0]
    assert tasks is None
    assert not registration.enabled
    assert registration.argument_validator is None
    assert registration.handler is None


def test_enabled_knowledge_defines_rewrite_and_summary_before_gateway_freeze() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)

    assert tasks is not None
    assert tuple(item.task_id.value for item in tasks.as_tuple()) == ("knowledge_rewrite", "knowledge_summary")
    assert tuple(item.task_version for item in tasks.as_tuple()) == ("5", "4")
