"""Consumed fake runner fixtures cannot hide current V10 production regressions."""
from types import SimpleNamespace
import sys

import agent_runtime.bootstrap as bootstrap
import agent_runtime.main as main
from tests.integration.knowledge import test_requirement_runtime_composition as current
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared
from tests.system_e2e.conftest import isolate_consumed_representative_root


def test_exact_consumed_binding_restores_current_root_and_helper(monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    request = SimpleNamespace(
        module=SimpleNamespace(__name__="tests.system_e2e.test_knowledge_representative_uat_v3", production=current),
        function=SimpleNamespace(__name__="test_current_9_7_real_decoders_and_safe_evidence"),
    )
    assert root.task_definitions(enabled=True).rewrite.task_version == "10"
    with monkeypatch.context() as patch:
        isolate_consumed_representative_root.__wrapped__(request, patch)
        frozen = bootstrap.KnowledgeCompositionRoot
        tasks = frozen.task_definitions(enabled=True)
        assert (tasks.rewrite.task_version, tasks.summary.task_version) == ("9", "7")
        assert frozen is main.KnowledgeCompositionRoot and frozen is not root
        assert shared.production is request.module.production is sys.modules[current.__name__]
        assert shared.production.KnowledgeCompositionRoot is frozen
    assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is root
    assert shared.production is request.module.production is sys.modules[current.__name__] is current
    assert root.task_definitions(enabled=True).rewrite.task_version == "10"


def test_other_test_or_module_never_uses_frozen_root(monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    for module, function in (
        ("tests.system_e2e.test_knowledge_representative_uat_v3", "unrelated_current_test"),
        ("tests.integration.knowledge.test_requirement_runtime_composition", "test_current_9_7_real_decoders_and_safe_evidence"),
        ("tests.system_e2e.test_knowledge_representative_uat_v4", "test_current_9_7_real_decoders_and_safe_evidence"),
    ):
        request = SimpleNamespace(module=SimpleNamespace(__name__=module), function=SimpleNamespace(__name__=function))
        isolate_consumed_representative_root.__wrapped__(request, monkeypatch)
        assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is root
        assert shared.production is sys.modules[current.__name__] is current
