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


def bind_consumed_entrypoint_imports(monkeypatch, build):
    # These source-frozen runners captured the entrypoint with `from ... import`.
    # Only the exact consumed-test fixtures call this; no current harness opts in.
    for name in ("tests.system_e2e.knowledge_stage_b_uat", "tests.system_e2e.knowledge_activation_local_smoke"):
        module = sys.modules.get(name)
        if module is not None:
            monkeypatch.setattr(module, "build_runtime", build)


@pytest.fixture(autouse=True)
def isolate_historical_stub_composition(request, monkeypatch):
    # This immutable stub/employee.detail harness is not the current Spring E2E.
    if (request.module.__name__ != "tests.system_e2e.test_runtime_composition" or request.function.__name__ !=
            "test_test_only_composition_uses_stub_and_rejects_invalid_local_arguments_without_network"):
        return
    import agent_runtime.bootstrap as bootstrap
    from tests.system_e2e import runtime_server
    repo = Path(__file__).resolve().parents[3]
    head = "c07bb23b49665607897ad5a4a6e079e36d2584a6"
    paths = {
        "agent-runtime/src/agent_runtime/bootstrap.py": "e4572dafab3bef52db1efdb35cd6e3f6ccb01e886b81f3d571f211e6cec95e0c",
        "agent-runtime/tests/system_e2e/runtime_server.py": "987b30c3feb88d67b83c5f856fcd39d901e0bd366f2be53fca7328ebba95f1dc",
        "agent-runtime/tests/system_e2e/test_runtime_composition.py": "352f4c05190f7173ddd543dbd4c23d9ba289fe37c81fe4724116db509ee883f7",
    }
    source = None
    for path, expected in paths.items():
        raw = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        assert hashlib.sha256(raw).hexdigest() == expected
        if path.endswith("/bootstrap.py"):
            source = raw
        else:
            assert (repo / path).read_bytes() == raw
    assert source is not None
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    assert len(nodes) == 1
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:KnowledgeCompositionRoot", "exec"), namespace)
    monkeypatch.setattr(runtime_server, "KnowledgeCompositionRoot", namespace["KnowledgeCompositionRoot"])


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
    from tests.integration.knowledge.conftest import frozen_entrypoint
    main_path = "agent-runtime/src/agent_runtime/main.py"
    main_source = subprocess.check_output(["git", "show", f"{head}:{main_path}"], cwd=repo)
    assert hashlib.sha256(main_source).hexdigest() == manifest["assets"][main_path]
    monkeypatch.setattr(main, "build_runtime", frozen_entrypoint(head, main_source))
    bind_consumed_entrypoint_imports(monkeypatch, main.build_runtime)
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
def isolate_consumed_representative_root(request, monkeypatch):
    """Frozen 9/7 runner tests use their source binding, never today's root."""
    targets = {
        f"tests.system_e2e.test_knowledge_representative_uat_v{version}": {
            "test_current_9_7_real_decoders_and_safe_evidence",
            "test_failure_never_passes_retries_or_leaks",
            "test_cancellation_closes_clients_keeps_attempt",
        } for version in (1, 2, 3)
    }
    targets["tests.system_e2e.test_knowledge_representative_uat_v3"].add(
        "test_failure_projection_is_wired_to_actual_runner_without_raw_data")
    for version in (1, 2, 3):
        targets[f"tests.system_e2e.test_knowledge_representative_human_uat_v{version}"] = {
            "test_actual_current_root_decoders_then_human_wait_make_no_extra_outbound"}
    targets["tests.system_e2e.test_knowledge_representative_failure_observation"] = {
        "test_observer_preserves_current_root_result_counts_and_safe_evidence",
        "test_current_runner_cancellation_restores_observer_and_closes_clients",
    }
    if request.function.__name__ not in targets.get(request.module.__name__, set()):
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main
    import tests.integration.knowledge as package
    from tests.system_e2e import test_knowledge_representative_uat_v1 as shared

    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((Path(__file__).parent / "knowledge_representative_human_run_06/manifest.json").read_bytes())
    head = manifest["frozenHead"]
    assert head == "b83d877e13593ed0a6a0655cc9661ae025b665ad"
    helper = "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"

    def frozen(path):
        source = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        # The fake helper is pinned separately; it was not a live manifest asset.
        expected = ("49af9fd1595c2323a374ae1c8757ddfb9ea51f2f356be215674d1cb7be29edcc"
                    if path == helper else manifest["assets"][path])
        assert hashlib.sha256(source).hexdigest() == expected
        return source.decode("utf-8")

    nodes = [node for node in ast.parse(frozen("agent-runtime/src/agent_runtime/bootstrap.py")).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    assert len(nodes) == 1
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:KnowledgeCompositionRoot", "exec"), namespace)
    root = namespace["KnowledgeCompositionRoot"]
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    from tests.integration.knowledge.conftest import frozen_entrypoint
    monkeypatch.setattr(main, "build_runtime", frozen_entrypoint(head, frozen("agent-runtime/src/agent_runtime/main.py")))
    bind_consumed_entrypoint_imports(monkeypatch, main.build_runtime)
    name = "tests.integration.knowledge.test_requirement_runtime_composition"
    module = ModuleType(name)
    module.__file__ = str(repo / helper)
    exec(compile(frozen(helper), f"git:{head}:{name}", "exec"), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(package, "test_requirement_runtime_composition", module, raising=False)
    monkeypatch.setattr(shared, "production", module)
    if hasattr(request.module, "production"):
        monkeypatch.setattr(request.module, "production", module)


@pytest.fixture(autouse=True)
def isolate_consumed_flash_root(request, monkeypatch):
    targets = {
        "tests.system_e2e.test_knowledge_representative_human_uat_v4": {
            "test_actual_current_root_decoders_then_human_wait_make_no_extra_outbound",
            "test_current_root_failures_preserve_zero_calls_and_no_leak",
        },
        "tests.system_e2e.test_knowledge_model_failure_probe_v1": {
            "test_current_runtime_stops_before_retrieval_and_preserves_observations"},
        "tests.system_e2e.test_knowledge_model_failure_probe_v2": {
            "test_current_root_outcome_and_calls_are_unchanged"},
        "tests.system_e2e.test_knowledge_model_failure_probe_v3": {
            "test_current_production_root_rejects_with_zero_downstream"},
    }
    if request.function.__name__ not in targets.get(request.module.__name__, set()):
        return
    from tests.integration.knowledge.conftest import frozen_v10_fixture
    from tests.system_e2e import test_knowledge_representative_uat_v1 as shared
    module = frozen_v10_fixture(monkeypatch)
    bind_consumed_entrypoint_imports(monkeypatch, module.build_runtime)
    monkeypatch.setattr(shared, "production", module)
    if request.module.__name__ == "tests.system_e2e.test_knowledge_representative_human_uat_v4":
        monkeypatch.setattr(request.module.base.service_run, "build_runtime", module.build_runtime)
    if request.module.__name__ != "tests.system_e2e.test_knowledge_representative_human_uat_v4" and hasattr(request.module, "invoke"):
        monkeypatch.setattr(request.module, "invoke", module.invoke)
    if hasattr(request.module, "production"):
        monkeypatch.setattr(request.module, "production", module)


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
    bind_consumed_entrypoint_imports(monkeypatch, build)
    for name in ("tests.integration.knowledge.test_rewrite_v4_provider_boundary",
                 "tests.integration.knowledge.test_requirement_runtime_composition"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "build_runtime"):
            monkeypatch.setattr(module, "build_runtime", build)
