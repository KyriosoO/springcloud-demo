from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = RUNTIME_ROOT.parent
GENERATOR = RUNTIME_ROOT / "scripts" / "target_contract" / "generate_contract_models.py"
FIXTURE_DIR = (
    REPO_ROOT / "agent-api" / "src" / "test" / "resources"
    / "contract" / "candidate" / "fixtures"
)


@pytest.fixture(scope="session")
def candidate_models(tmp_path_factory: pytest.TempPathFactory) -> ModuleType:
    output = tmp_path_factory.mktemp("candidate-contract") / "generated_models.py"
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output)],
        cwd=RUNTIME_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    spec = importlib.util.spec_from_file_location("candidate_generated_models", output)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def candidate_fixture_dir() -> Path:
    assert FIXTURE_DIR.is_dir(), f"fixture directory not found: {FIXTURE_DIR}"
    return FIXTURE_DIR
