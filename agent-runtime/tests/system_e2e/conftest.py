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
    if (request.module.__name__ != "tests.system_e2e.test_knowledge_stage_b_uat_v8"
            or request.function.__name__ != "test_capture_hooks_on_actual_current_production_root_and_provider_wire"):
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main
    import tests.integration.knowledge as package

    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((Path(__file__).parent / "knowledge_stage_b_run_08" / "manifest.json").read_bytes())
    head = manifest["frozenHead"]

    def frozen(path):
        source = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        # The fake helper was not a live execution asset. Pin its source at the
        # same frozen commit separately; do not invent an entry in the manifest.
        helper = "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"
        expected = ("9d456883c1d65baef30d0151dc6ce0ae34f3ff6a71035b5a8ffe701dbc8bfde1"
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
    name = "tests.integration.knowledge.test_requirement_runtime_composition"
    module = ModuleType(name)
    module.__file__ = str(repo / "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py")
    exec(compile(frozen("agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"),
                 f"git:{head}:{name}", "exec"), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(package, "test_requirement_runtime_composition", module, raising=False)
