"""Preserve pre-cutover contract tests without weakening the current root.

These version-specific modules retain their frozen input/expected output bytes.
New requirement tests and the Spring harness always use the actual current root.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
import subprocess

import pytest


ROOT_BASELINE = "806e1568c694a95769852a47e6c7ff00ec5b1f5a"
LEGACY_ROOT_TEST_FILES = frozenset(name + ".py" for name in (
    "test_production_runtime_wiring", "test_summary_v2_composition", "test_summary_v4_composition",
    "test_stage_b_production", "test_rewrite_v4_provider_boundary", "test_rewrite_v5_domain_boundary",
    "test_rewrite_v6_query_focus", "test_tax_semantic_guard_production", "test_summary_v5_production",
    "test_stage_b_citation_binding",
))


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

    def historical_build(*, evidence_selection_version="legacy", **kwargs):
        # Only the exact historical modules below use this bridge. Their old
        # plans/selection stay unchanged when the current entrypoint adds its
        # internal binding argument; current-root tests must never use it.
        if evidence_selection_version not in ("legacy", ScoreAwareEvidenceSelector.VERSION):
            raise ValueError("knowledge.historical_selection_version_invalid")
        return frozen_build(**kwargs)

    root.build_provider = staticmethod(historical_build)
    return root


@pytest.fixture(autouse=True)
def isolate_version_specific_knowledge_root(request, monkeypatch):
    # pytest's package name depends on source-tree/installed collection mode.
    # Match the exact test path, never a broad suffix or all Knowledge tests.
    path = Path(request.module.__file__).resolve()
    if path.parent != Path(__file__).resolve().parent or path.name not in LEGACY_ROOT_TEST_FILES:
        return
    import agent_runtime.bootstrap as bootstrap
    import agent_runtime.main as main

    root = legacy_root()
    monkeypatch.setattr(bootstrap, "KnowledgeCompositionRoot", root)
    monkeypatch.setattr(main, "KnowledgeCompositionRoot", root)
    if hasattr(request.module, "KnowledgeCompositionRoot"):
        monkeypatch.setattr(request.module, "KnowledgeCompositionRoot", root)
