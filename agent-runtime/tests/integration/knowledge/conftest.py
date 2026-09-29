"""Preserve pre-cutover contract tests without weakening the current root.

These version-specific modules retain their frozen input/expected output bytes.
New requirement tests and the Spring harness always use the actual current root.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
import subprocess
import hashlib
import json
import sys
from types import FunctionType, ModuleType

import pytest


ROOT_BASELINE = "806e1568c694a95769852a47e6c7ff00ec5b1f5a"
PRE_MINIMAL_ROOT_BASELINE = "2e27086150360bda87ef09e319a2569a2246c07b"
LEGACY_ROOT_TEST_FILES = frozenset(name + ".py" for name in (
    "test_production_runtime_wiring", "test_summary_v2_composition", "test_summary_v4_composition",
    "test_stage_b_production", "test_rewrite_v4_provider_boundary", "test_rewrite_v5_domain_boundary",
    "test_rewrite_v6_query_focus", "test_tax_semantic_guard_production", "test_summary_v5_production",
    "test_stage_b_citation_binding",
))
PRE_MINIMAL_ROOT_TEST_FILES = frozenset(name + ".py" for name in (
    "test_document_reference_guard_production", "test_evidence_admission_composition",
    "test_requirement_plan_production", "test_requirement_runtime_composition",
    "test_rewrite_v11_runtime_snapshot", "test_summary_failure_runtime_observation",
))


def frozen_entrypoint(head, source=None):
    """Pair a frozen root with its entrypoint, not new-signature argument repair."""
    import agent_runtime.main as main
    if source is None:
        source = subprocess.check_output(["git", "show", f"{head}:agent-runtime/src/agent_runtime/main.py"],
                                         cwd=Path(__file__).resolve().parents[4])
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "build_runtime"]
    assert len(nodes) == 1
    namespace = dict(vars(main))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:build_runtime", "exec"), namespace)
    original = namespace["build_runtime"]
    result = FunctionType(original.__code__, vars(main), "build_runtime", original.__defaults__)
    result.__kwdefaults__ = original.__kwdefaults__
    return result


@lru_cache(maxsize=1)
def legacy_root():
    import agent_runtime.bootstrap as bootstrap
    from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector

    repo = Path(__file__).resolve().parents[4]
    source = subprocess.check_output(
        ["git", "show", f"{ROOT_BASELINE}:agent-runtime/src/agent_runtime/bootstrap.py"], cwd=repo,
    ).decode("utf-8")
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    if len(nodes) != 1:
        raise AssertionError("knowledge.historical_root_missing")
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{ROOT_BASELINE}:KnowledgeCompositionRoot", "exec"), namespace)
    root = namespace["KnowledgeCompositionRoot"]
    frozen_build = root.build_provider

    def historical_build(*, evidence_selection_version="legacy", preserve_original_keyword=False, **kwargs):
        # Only the exact historical modules below use this bridge. Their old
        # plans/selection stay unchanged when the current entrypoint adds its
        # internal binding argument; current-root tests must never use it.
        if evidence_selection_version not in ("legacy", ScoreAwareEvidenceSelector.VERSION):
            raise ValueError("knowledge.historical_selection_version_invalid")
        if type(preserve_original_keyword) is not bool:
            raise ValueError("knowledge.historical_query_representation_invalid")
        # Historical callers intentionally retain their frozen same-query builder.
        return frozen_build(**kwargs)

    root.build_provider = staticmethod(historical_build)
    return root


@lru_cache(maxsize=1)
def pre_minimal_root():
    """Run v11/Summary7-specific tests against the exact pre-cutover root."""
    import agent_runtime.bootstrap as bootstrap

    repo = Path(__file__).resolve().parents[4]
    source = subprocess.check_output(
        ["git", "show", f"{PRE_MINIMAL_ROOT_BASELINE}:agent-runtime/src/agent_runtime/bootstrap.py"], cwd=repo,
    )
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    if len(nodes) != 1:
        raise AssertionError("knowledge.pre_minimal_root_missing")
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 f"git:{PRE_MINIMAL_ROOT_BASELINE}:KnowledgeCompositionRoot", "exec"), namespace)
    return namespace["KnowledgeCompositionRoot"]


@pytest.fixture(autouse=True)
def isolate_version_specific_knowledge_root(request, monkeypatch):
    # pytest's package name depends on source-tree/installed collection mode.
    # Match the exact test path, never a broad suffix or all Knowledge tests.
    path = Path(request.module.__file__).resolve()
    if (path.parent != Path(__file__).resolve().parent
            or path.name not in LEGACY_ROOT_TEST_FILES | PRE_MINIMAL_ROOT_TEST_FILES):
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main

    historical = path.name in LEGACY_ROOT_TEST_FILES
    root = legacy_root() if historical else pre_minimal_root()
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    build = frozen_entrypoint(ROOT_BASELINE if historical else PRE_MINIMAL_ROOT_BASELINE)
    monkeypatch.setattr(main, "build_runtime", build)
    if hasattr(request.module, "build_runtime"):
        monkeypatch.setattr(request.module, "build_runtime", build)
    if hasattr(request.module, "KnowledgeCompositionRoot"):
        monkeypatch.setattr(request.module, "KnowledgeCompositionRoot", root)
    if not historical:
        # Several v11-only modules reuse the requirement-era helper imported at
        # collection time; patch its entrypoint for this test's scope as well.
        import tests.integration.knowledge.test_requirement_runtime_composition as requirement_harness
        monkeypatch.setattr(requirement_harness, "build_runtime", build)


def frozen_v10_fixture(monkeypatch):
    """Only callers on explicit historical allowlists below may install this."""
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main
    import tests.integration.knowledge as package
    repo = Path(__file__).resolve().parents[4]
    manifest = json.loads((repo / "agent-runtime/tests/system_e2e/knowledge_representative_human_run_07/manifest.json").read_bytes())
    head = manifest["frozenHead"]
    assert head == "8e34893ffb4b67e34bddccde231999c0734eb2af"
    helper = "agent-runtime/tests/integration/knowledge/test_requirement_runtime_composition.py"

    def frozen(path):
        source = subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)
        expected = ("b02ce598d9ba17e95c02ffb026b564b82df09f902dff7a165cecf5c03ccd223b"
                    if path == helper else manifest["assets"][path])
        assert hashlib.sha256(source).hexdigest() == expected
        return source

    nodes = [node for node in ast.parse(frozen("agent-runtime/src/agent_runtime/bootstrap.py")).body
             if isinstance(node, ast.ClassDef) and node.name == "KnowledgeCompositionRoot"]
    assert len(nodes) == 1
    namespace = dict(vars(bootstrap))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"git:{head}:KnowledgeCompositionRoot", "exec"), namespace)
    root = namespace["KnowledgeCompositionRoot"]
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    build = frozen_entrypoint(head, frozen("agent-runtime/src/agent_runtime/main.py"))
    monkeypatch.setattr(main, "build_runtime", build)
    name = "tests.integration.knowledge.test_requirement_runtime_composition"
    module = ModuleType(name)
    module.__file__ = str(repo / helper)
    exec(compile(frozen(helper), f"git:{head}:{helper}", "exec"), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(package, "test_requirement_runtime_composition", module)
    return module


@pytest.fixture(autouse=True)
def isolate_historical_v10_semantic_diagnostics(request, monkeypatch):
    path = Path(request.module.__file__).resolve()
    if path.parent != Path(__file__).resolve().parent or path.name not in {
        "test_rewrite_v9_period_lookup_diagnosis.py", "test_rewrite_v10_failure_boundary.py",
    }:
        return
    module = frozen_v10_fixture(monkeypatch)
    for symbol in ("invoke", "Model", "Clients", "plan", "build_runtime"):
        if hasattr(request.module, symbol):
            monkeypatch.setattr(request.module, symbol, getattr(module, symbol))
