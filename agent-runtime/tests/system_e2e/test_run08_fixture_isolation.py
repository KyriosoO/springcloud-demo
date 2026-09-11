"""A frozen fake runner cannot silently change the current production root."""
from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

import agent_runtime.bootstrap as bootstrap
import agent_runtime.main as main
from tests.integration.knowledge import test_requirement_runtime_composition as current
from tests.system_e2e.conftest import isolate_consumed_entrypoint_signature, isolate_consumed_run08_root_fixture


def test_historical_stub_isolation_never_replaces_current_main_or_other_tests(monkeypatch):
    from tests.system_e2e import runtime_server
    from tests.system_e2e.conftest import isolate_historical_stub_composition
    root, build, stub_root = bootstrap.KnowledgeCompositionRoot, main.build_runtime, runtime_server.KnowledgeCompositionRoot
    request = SimpleNamespace(module=SimpleNamespace(__name__="tests.system_e2e.test_runtime_composition"),
        function=SimpleNamespace(__name__="test_test_only_composition_uses_stub_and_rejects_invalid_local_arguments_without_network"))
    with monkeypatch.context() as patch:
        isolate_historical_stub_composition.__wrapped__(request, patch)
        tasks = runtime_server.KnowledgeCompositionRoot.task_definitions(enabled=True)
        assert (tasks.rewrite.task_version, tasks.summary.task_version) == ("1", "2")
        assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is root
        assert main.build_runtime is build
    assert runtime_server.KnowledgeCompositionRoot is stub_root
    request.function.__name__ = "unrelated_test"
    isolate_historical_stub_composition.__wrapped__(request, monkeypatch)
    assert runtime_server.KnowledgeCompositionRoot is stub_root


def test_only_exact_consumed_test_uses_frozen_source_and_restores(monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    name = current.__name__
    assert root.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",)).rewrite.task_version == "11"
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
    assert root.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",)).rewrite.task_version == "11"


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


@pytest.mark.parametrize("module,function", [
    ("tests.system_e2e.test_knowledge_current_chain_v1",
     "test_full_current_root_uses_actual_wire_planning_and_post_source_binding"),
    ("tests.system_e2e.test_knowledge_stage_b_uat_v12",
     "test_current_root_capture_provider_wire_and_context_observer"),
])
def test_consumed_v8_binding_is_exact_and_current_v9_is_restored(module, function, monkeypatch):
    root = bootstrap.KnowledgeCompositionRoot
    test_module = SimpleNamespace(__name__=module, production=current)
    request = SimpleNamespace(module=test_module, function=SimpleNamespace(__name__=function))
    assert root.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",)).rewrite.task_version == "11"
    with monkeypatch.context() as patch:
        isolate_consumed_run08_root_fixture.__wrapped__(request, patch)
        frozen = bootstrap.KnowledgeCompositionRoot
        tasks = frozen.task_definitions(enabled=True)
        assert (tasks.rewrite.task_version, tasks.summary.task_version) == ("8", "7")
        assert frozen is main.KnowledgeCompositionRoot and frozen is not root
        assert sys.modules[current.__name__].KnowledgeCompositionRoot is frozen
        if module.endswith("test_knowledge_current_chain_v1"):
            assert test_module.production is not current
    assert bootstrap.KnowledgeCompositionRoot is main.KnowledgeCompositionRoot is root
    assert sys.modules[current.__name__] is current and test_module.production is current
    request.function.__name__ = "unrelated_current_test"
    isolate_consumed_run08_root_fixture.__wrapped__(request, monkeypatch)
    assert bootstrap.KnowledgeCompositionRoot is root


def test_run12_entrypoint_and_helper_are_restored_with_current_root(monkeypatch):
    root, build, helper_build = bootstrap.KnowledgeCompositionRoot, main.build_runtime, current.build_runtime
    request = SimpleNamespace(
        module=SimpleNamespace(
            __name__="tests.system_e2e.test_knowledge_stage_b_uat_v12",
            __file__=str(Path(__file__).with_name("test_knowledge_stage_b_uat_v12.py")),
        ),
        function=SimpleNamespace(__name__="test_current_root_capture_provider_wire_and_context_observer"),
    )
    with monkeypatch.context() as patch:
        isolate_consumed_run08_root_fixture.__wrapped__(request, patch)
        isolate_consumed_entrypoint_signature.__wrapped__(request, patch, None)
        assert main.build_runtime is not build
        assert sys.modules[current.__name__].build_runtime is main.build_runtime
        assert bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=True).rewrite.task_version == "8"
    assert bootstrap.KnowledgeCompositionRoot is root and main.build_runtime is build
    assert current.build_runtime is helper_build and sys.modules[current.__name__] is current
    request.function.__name__ = "unrelated_current_test"
    isolate_consumed_entrypoint_signature.__wrapped__(request, monkeypatch, None)
    assert main.build_runtime is build
