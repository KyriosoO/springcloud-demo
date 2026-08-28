from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast


_ROOT = Path(__file__).resolve().parents[4]
_FROZEN_HEAD = "3222e59ce82d664b51b5ae3d9e1a3737b206f9a3"
_RUN_ID = "employee-natural-language-v1-20260828-candidate-01"
_MANIFEST_SHA256 = "e5a39d3f67af8d7bc0799b0a701265fe42b6bcce0239a65880244fcb99e03091"
_FILES = {
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-01.manifest.json": _MANIFEST_SHA256,
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-01.authorization.json": "e3b54613a1425c06a12ad60d693e31de61ceee5f57faed3a6d8cdf7a668511c1",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-01/authorization.consumed.json": "c7309bdaa2481d20d4a8664146037785511aa56e5e8eee1a0bbf2cfbca4861a7",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-01/attempts.jsonl": "65ce0b003ae942e60b517c42106b0f7b1093924498c7260973e0c069d9398002",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-01/lifecycle.jsonl": "2c872064443dc4f5e13963b46c632ce4efd672708b620b43358b37f51802e379",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-01/result.json": "4671df96305455f6696765814d91752742242d1295adfbef375bdc2f6cd13625",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-01/launcher-evidence.json": "94a61bff9b02a4e4be696ecd2682c122b2c077701adb0eff300a9e0e3dc7e7e1",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_01_consumed_failure_assets_are_immutable() -> None:
    for relative, expected in _FILES.items():
        assert _sha256(_ROOT / relative) == expected

    result = cast(
        dict[str, object],
        json.loads((_ROOT / next(path for path in _FILES if path.endswith("/result.json"))).read_text(encoding="utf-8")),
    )
    counts = cast(dict[str, object], result["counts"])
    assert result["status"] == "failed_consumed"
    assert result["runId"] == _RUN_ID
    assert result["frozenHead"] == _FROZEN_HEAD
    assert result["manifestSha256"] == _MANIFEST_SHA256
    assert counts == {
        "answer": 0,
        "employeeSearchCalls": 0,
        "employeeSemantic": 0,
        "knowledge": 0,
        "modelCalls": 1,
        "otherEmployeeEndpoints": 0,
        "resume": 0,
        "retry": 0,
        "transaction": 0,
    }


def test_candidate_01_manifest_source_assets_remain_recoverable_from_frozen_head() -> None:
    manifest_path = next(path for path in _FILES if path.endswith(".manifest.json"))
    manifest = cast(
        dict[str, object],
        json.loads((_ROOT / manifest_path).read_text(encoding="utf-8")),
    )
    for raw in cast(list[object], manifest["assets"]):
        asset = cast(dict[str, str], raw)
        completed = subprocess.run(
            ["git", "show", f"{_FROZEN_HEAD}:{asset['path']}"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
        )
        assert hashlib.sha256(completed.stdout).hexdigest() == asset["sha256"]
