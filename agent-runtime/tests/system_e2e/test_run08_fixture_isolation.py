"""A frozen fake runner cannot silently change the current production root."""
from types import SimpleNamespace
import sys

import agent_runtime.bootstrap as bootstrap
import agent_runtime.main as main
from tests.integration.knowledge import test_requirement_runtime_composition as current
from tests.system_e2e.conftest import isolate_consumed_run08_root_fixture


def test_only_exact_consumed_test_uses_frozen_source_and_restores(monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    name = current.__name__
    assert root.task_definitions(enabled=True).rewrite.task_version == "8"
    request = SimpleNamespace(
        module=SimpleNamespace(__name__="tests.system_e2e.test_knowledge_stage_b_uat_v8"),
        function=SimpleNamespace(__name__="test_capture_hooks_on_actual_current_production_root_and_provider_wire"),
    )
    with monkeypatch.context() as patch:
        isolate_consumed_run08_root_fixture.__wrapped__(request, patch)
        frozen = bootstrap.KnowledgeCompositionRoot
        assert frozen is main.KnowledgeCompositionRoot and frozen is not root
        assert frozen.task_definitions(enabled=True).rewrite.task_version == "7"
        assert sys.modules[name] is not current
        assert sys.modules[name].KnowledgeCompositionRoot is frozen
    assert bootstrap.KnowledgeCompositionRoot is root and main.KnowledgeCompositionRoot is root
    assert sys.modules[name] is current
    assert root.task_definitions(enabled=True).rewrite.task_version == "8"


def test_other_test_in_same_module_keeps_current_root(monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    for module, function in (
        ("tests.system_e2e.test_knowledge_stage_b_uat_v8", "any_other_test"),
        ("different.module", "test_capture_hooks_on_actual_current_production_root_and_provider_wire"),
    ):
        request = SimpleNamespace(module=SimpleNamespace(__name__=module), function=SimpleNamespace(__name__=function))
        isolate_consumed_run08_root_fixture.__wrapped__(request, monkeypatch)
        assert bootstrap.KnowledgeCompositionRoot is root
        assert sys.modules[current.__name__] is current
