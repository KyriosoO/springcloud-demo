from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

import knowledge_corpus_tools
import agent_runtime


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run-nonlive-regression.ps1"


def test_nonlive_regression_bootstrap_installs_current_source_in_isolated_venv() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "-m venv --system-site-packages" in text
    assert "'setuptools==80.9.0'" in text
    assert '-m pip install --disable-pip-version-check --no-build-isolation "${runtimeRoot}[test]"' in text
    assert "--no-deps" not in text
    assert "tests/integration/adapters/transaction/test_transaction_egress_candidate_v3_host.py" in text
    assert "tests/integration/adapters/transaction/test_transaction_egress_candidate_v4_host.py" in text
    assert "& $isolatedPython -m pytest" in text


def test_nonlive_regression_bootstrap_cleans_only_its_owned_temporary_directory() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[IO.Path]::GetTempPath()" in text
    assert text.count("agent-runtime-nonlive-") >= 3
    assert "Resolve-Path -LiteralPath $runRoot" in text
    assert "Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force" in text
    assert "git clean" not in text
    assert "reset --hard" not in text


def test_nonlive_regression_bootstrap_removes_pythonpath_for_reproducibility() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$previousPythonPath" in text
    assert "SetEnvironmentVariable('PYTHONPATH', $null, 'Process')" in text
    assert "SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')" in text


def test_nonlive_evaluation_imports_current_sibling_source() -> None:
    source = ROOT.parent / "knowledge-corpus-tools/src/knowledge_corpus_tools/__init__.py"
    assert Path(knowledge_corpus_tools.__file__).resolve() == source.resolve()
    assert Path(agent_runtime.__file__).resolve() == (ROOT / "src/agent_runtime/__init__.py").resolve()


def test_nonlive_snapshot_import_does_not_load_document_parsers() -> None:
    subprocess.run(
        [sys.executable, "-c", "import sys; "
         "from knowledge_corpus_tools import document_number_snapshot_v1; "
         "assert 'knowledge_corpus_tools.parsing' not in sys.modules"],
        env={**os.environ, "PYTHONPATH": str(ROOT.parent / "knowledge-corpus-tools/src")},
        capture_output=True, text=True, check=True, timeout=30,
    )
