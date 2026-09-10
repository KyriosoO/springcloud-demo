"""Test-only historical inputs; consumed runners and validators stay immutable."""
from __future__ import annotations

import subprocess
import ast
import json
import hashlib
from pathlib import Path
import sys
from types import FunctionType, ModuleType

import pytest


def frozen_run07_compatible_manifest():
    from tests.system_e2e import knowledge_stage_b_uat as old
    from tests.system_e2e import knowledge_stage_b_uat_v7 as run07

    value, _ = run07.run06_assets()
    for name in run07.COMPATIBLE_CHANGES:
        source = subprocess.check_output(
            ["git", "show", f"{run07.COMPATIBLE_HEAD}:{name}"], cwd=old.REPO,
        )
        value["assets"][name] = old.digest(source)
    return value


@pytest.fixture(autouse=True)
def isolate_consumed_run07_test_input(request, monkeypatch):
    # Only replace fixture preparation, never a validator, assertion or live runner.
    if request.module.__name__ == "tests.system_e2e.test_knowledge_stage_b_uat_v7":
        monkeypatch.setattr(request.module, "compatible_manifest", frozen_run07_compatible_manifest)


@pytest.fixture(autouse=True)
def isolate_consumed_run08_root_fixture(request, monkeypatch):
    """Only the consumed runner's source-bound fake test uses its frozen root."""
    run08 = (request.module.__name__ == "tests.system_e2e.test_knowledge_stage_b_uat_v8"
             and request.function.__name__ == "test_capture_hooks_on_actual_current_production_root_and_provider_wire")
    run09_10 = (request.module.__name__ in {"tests.system_e2e.test_knowledge_stage_b_uat_v9",
                                          "tests.system_e2e.test_knowledge_stage_b_uat_v10"}
                and request.function.__name__ == "test_current_root_capture_provider_wire_and_context_observer")
    run12 = (request.module.__name__ == "tests.system_e2e.test_knowledge_stage_b_uat_v12"
             and request.function.__name__ == "test_current_root_capture_provider_wire_and_context_observer")
    consumed_v8_tests = {
        "tests.system_e2e.test_knowledge_current_chain_v1": {
            "test_full_current_root_uses_actual_wire_planning_and_post_source_binding",
            "test_failure_never_passes_or_retries_and_remains_finite",
            "test_cancel_preserves_attempt_and_restores_observers",
            "test_sensitive_input_zero_wire_and_zero_local",
        },
        "tests.system_e2e.test_knowledge_activation_local_smoke": {
            "test_current_root_fake_summary_no_answer_and_finite_observation",
            "test_partial_vector_failure_cannot_pass_complete_integration",
            "test_sensitive_input_no_model_or_transport",
        },
        "tests.system_e2e.test_knowledge_summary_diagnostic_v1": {
            "test_current_root_real_transport_decoder_and_postvalidation_finite",
            "test_cancelled_real_transport_closes_client_and_restores_validator",
        },
    }
    current_chain = request.function.__name__ in consumed_v8_tests.get(request.module.__name__, set())
    if not (run08 or run09_10 or run12 or current_chain):
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main
    import tests.integration.knowledge as package

    repo = Path(__file__).resolve().parents[3]
    directory = ("knowledge_stage_b_run_08" if run08 else "knowledge_stage_b_run_12" if run12
                 else "knowledge_current_chain_01" if current_chain else "knowledge_stage_b_run_11")
    manifest = json.loads((Path(__file__).parent / directory / "manifest.json").read_bytes())
    head = manifest["frozenHead"]

    def frozen(path):
        source = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        # The fake helper was not a live execution asset. Pin its source at the
        # same frozen commit separately; do not invent an entry in the manifest.
        helper = "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"
        if run12 or current_chain:
            assert head == ("05ffadd353eb7299849e1c63893bb18fc6671f66" if run12
                            else "44cfb95b018dae508662e61184894422f1f2fe83")
            expected = ("d5624553a8cff7bd9838f41190442afade6d28ef5993325f2718950b99f16e5a"
                        if path == helper else manifest["assets"][path])
        elif run08:
            expected = ("9d456883c1d65baef30d0151dc6ce0ae34f3ff6a71035b5a8ffe701dbc8bfde1"
                        if path == helper else manifest["assets"][path])
        else:
            # Both historical tests require 8/6/v3. Pin Git blobs from run-11's
            # unchanged pair and verify against its exact recorded source hash.
            assert head == "09413f7bf0a0b3d34476b76b9db7571fbeb9b21e"
            expected = ("1be6f5415e7787c22e6b8a136835134cc53a14f2b3e10b93a8520aa07694b6d8"
                        if path == helper else "f2ca11c06dc9101297b4e1f46b070207ac3ee2fd32edf080032944d41e29e595")
            if path != helper:
                assert hashlib.sha256(source).hexdigest() == manifest["assets"][path]
        assert hashlib.sha256(source).hexdigest() == expected
        return source.decode("utf-8")

    nodes = [node for node in ast.parse(frozen("agent-runtime/src/agent_runtime/bootstrap.py")).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    assert len(nodes) == 1
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:KnowledgeCompositionRoot", "exec"), namespace)
    root = namespace["KnowledgeCompositionRoot"]
    if current_chain:
        frozen_build = root.build_provider

        def historical_build(*, preserve_original_keyword=False, **kwargs):
            # Exact consumed-test allowlist above only: keep the frozen v8
            # same-query plan, not the current entrypoint's new strategy.
            if type(preserve_original_keyword) is not bool:
                raise ValueError("knowledge.historical_query_representation_invalid")
            return frozen_build(**kwargs)

        root.build_provider = staticmethod(historical_build)
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    name = "tests.integration.knowledge.test_requirement_runtime_composition"
    module = ModuleType(name)
    module.__file__ = str(repo / "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py")
    exec(compile(frozen("agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"),
                 f"git:{head}:{name}", "exec"), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(package, "test_requirement_runtime_composition", module, raising=False)
    if current_chain:
        # 仅恢复已消费测试的显式导入；当前生产测试不使用冻结根，也不改旧断言。
        if hasattr(request.module, "production"):
            monkeypatch.setattr(request.module, "production", module)
        for symbol in ("Clients", "CONTENTS", "FOCUSES", "QUESTION"):
            if hasattr(request.module, symbol):
                monkeypatch.setattr(request.module, symbol, getattr(module, symbol))


@pytest.fixture(autouse=True)
def isolate_consumed_entrypoint_signature(request, monkeypatch, isolate_consumed_run08_root_fixture):
    # These tests already choose a frozen root. Pair it with the pre-admission
    # entrypoint instead of passing a new internal argument into an old root.
    targets = {
        ("test_knowledge_stage_b_uat_v3.py", "test_diagnostics_preserve_actual_wire_runtime_assertions"),
        ("test_knowledge_stage_b_uat_v4.py", "test_v5_diagnostics_with_current_production_root"),
        ("test_knowledge_stage_b_uat_v8.py", "test_capture_hooks_on_actual_current_production_root_and_provider_wire"),
        ("test_knowledge_stage_b_uat_v9.py", "test_current_root_capture_provider_wire_and_context_observer"),
        ("test_knowledge_stage_b_uat_v10.py", "test_current_root_capture_provider_wire_and_context_observer"),
        ("test_knowledge_stage_b_uat_v12.py", "test_current_root_capture_provider_wire_and_context_observer"),
    }
    path = Path(request.module.__file__).resolve()
    if path.parent != Path(__file__).resolve().parent or (path.name, request.function.__name__) not in targets:
        return
    import agent_runtime.main as main

    head = "17e1846d38064818db313fd8c4b7f01a4f6534ba"
    source = subprocess.run(["git", "show", f"{head}:agent-runtime/src/agent_runtime/main.py"],
                            cwd=path.parents[3], capture_output=True, timeout=10, check=True).stdout
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name == "build_runtime"]
    assert len(nodes) == 1
    namespace = dict(vars(main))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:build_runtime", "exec"), namespace)
    original = namespace["build_runtime"]
    # Preserve each test's subsequently selected historical root. No production
    # fallback or source rewrite; the complete old function comes from Git.
    build = FunctionType(original.__code__, vars(main), "build_runtime", original.__defaults__)
    build.__kwdefaults__ = original.__kwdefaults__
    monkeypatch.setattr(main, "build_runtime", build)
    for name in ("tests.integration.knowledge.test_rewrite_v4_provider_boundary",
                 "tests.integration.knowledge.test_requirement_runtime_composition"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "build_runtime"):
            monkeypatch.setattr(module, "build_runtime", build)
