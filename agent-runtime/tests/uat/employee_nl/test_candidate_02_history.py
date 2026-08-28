from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast


_ROOT = Path(__file__).resolve().parents[4]
_FROZEN_HEAD = "7231e23f2742d26319b719e254d28097f3fdc2ba"
_RUN_ID = "employee-natural-language-v1-20260828-candidate-02"
_MANIFEST_SHA256 = "eb274f884a78d06419a8365effa7a203a8aad15a6223176dba0602939941270b"
_FILES = {
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-02.manifest.json": _MANIFEST_SHA256,
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-02.authorization.json": "365bc682d94dfdcf742bd3e6eb5c98c5a5cf0a288704f6dfcc24dcadef29e99d",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-02/authorization.consumed.json": "21f68315e832e1fd6d89809d974207aa58725128e75258f90669ade11fa8b293",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-02/attempts.jsonl": "a1b7db706f4e32c4a3b867eeb007c3b25772f228a9247848c2a0a19656cccb54",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-02/lifecycle.jsonl": "300e20f3028bddf0f7731d5ec2ba80665faf99efbf4925208432cac1e092c5b2",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-02/result.json": "bb85b296bdbef0d7d29a306a3a6d73cbdf2b0327a0b85a35af2466d577bb3c63",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-02/launcher-evidence.json": "452225072f05237974f67ca0ca582847c30e75486c77a335549541bbd473c4b2",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_02_consumed_failure_assets_are_immutable() -> None:
    for relative, expected in _FILES.items():
        assert _sha256(_ROOT / relative) == expected

    result = cast(
        dict[str, object],
        json.loads((_ROOT / next(path for path in _FILES if path.endswith("/result.json"))).read_text(encoding="utf-8")),
    )
    counts = cast(dict[str, object], result["counts"])
    cases = cast(list[dict[str, object]], result["cases"])
    assert result["status"] == "failed_consumed"
    assert result["runId"] == _RUN_ID
    assert result["frozenHead"] == _FROZEN_HEAD
    assert result["manifestSha256"] == _MANIFEST_SHA256
    assert counts["modelCalls"] == 3
    assert counts["employeeSearchCalls"] == 2
    assert all(counts[name] == 0 for name in (
        "answer", "employeeSemantic", "knowledge", "otherEmployeeEndpoints",
        "resume", "retry", "transaction",
    ))
    assert [item["passed"] for item in cases] == [True, True, False]
    assert cases[-1]["status"] == "invalid_argument"
    assert cases[-1]["operators"] == ["prefix_any"]
    assert cases[-1]["valueShapes"] == ["value_refs"]


def test_candidate_02_manifest_source_assets_remain_recoverable_from_frozen_head() -> None:
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
