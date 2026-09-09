"""Test-only historical inputs; consumed runners and validators stay immutable."""
from __future__ import annotations

import subprocess
import ast
import json
import hashlib
from pathlib import Path
import sys
from types import ModuleType

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
    if not (run08 or run09_10):
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main
    import tests.integration.knowledge as package

    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((Path(__file__).parent / ("knowledge_stage_b_run_08" if run08 else "knowledge_stage_b_run_11") / "manifest.json").read_bytes())
    head = manifest["frozenHead"]

    def frozen(path):
        source = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        # The fake helper was not a live execution asset. Pin its source at the
        # same frozen commit separately; do not invent an entry in the manifest.
        helper = "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"
        if run08:
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
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    name = "tests.integration.knowledge.test_requirement_runtime_composition"
    module = ModuleType(name)
    module.__file__ = str(repo / "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py")
    exec(compile(frozen("agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"),
                 f"git:{head}:{name}", "exec"), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(package, "test_requirement_runtime_composition", module, raising=False)
