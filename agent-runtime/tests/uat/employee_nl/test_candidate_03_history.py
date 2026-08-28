from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast


_ROOT = Path(__file__).resolve().parents[4]
_FROZEN_HEAD = "054292478bb1feb45c76993292ed6fe09ff7ba17"
_RUN_ID = "employee-natural-language-v1-20260828-candidate-03"
_MANIFEST_SHA256 = "1beaea9c2ac864430e86db360df62a109a5e3be3bfcbc8f22d79852694b5cf71"
_FILES = {
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-03.manifest.json": _MANIFEST_SHA256,
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-03.authorization.json": "0b28037e323cd2d26dafd52e077ca6f06e0bc676532d8f388c3e57ad37e0f10b",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/authorization.consumed.json": "ab501bba694eb680ada30f0479105f57d600dff6484142f48dec456ab717335e",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/attempts.jsonl": "639acbbcd9ebc64f90304739ef62d408d0a19c8ca6eda38ce8b6125249457601",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/lifecycle.jsonl": "ce5b9e3bf8f30378cfe1ba1ffea87c8de2c4249db597f95f505bd0af8919adec",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/result.json": "b44a93a1c265634027a20d90fe416fa47e42acf6d95d989a8157753ccccf9ed5",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/launcher-evidence.json": "29d078c886a36baac5eaaaa2ff7c678836286bea2f9e6cef6e9cdb8ba3b21bc7",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_03_consumed_failure_assets_are_immutable() -> None:
    for relative, expected in _FILES.items():
        assert _sha256(_ROOT / relative) == expected

    result_path = next(path for path in _FILES if path.endswith("/result.json"))
    result = cast(
        dict[str, object],
        json.loads((_ROOT / result_path).read_text(encoding="utf-8")),
    )
    counts = cast(dict[str, object], result["counts"])
    cases = cast(list[dict[str, object]], result["cases"])
    assert result["status"] == "failed_consumed"
    assert result["runId"] == _RUN_ID
    assert result["frozenHead"] == _FROZEN_HEAD
    assert result["manifestSha256"] == _MANIFEST_SHA256
    assert counts["modelCalls"] == 14
    assert counts["employeeSearchCalls"] == 14
    assert all(
        counts[name] == 0
        for name in (
            "answer",
            "employeeSemantic",
            "knowledge",
            "otherEmployeeEndpoints",
            "resume",
            "retry",
            "transaction",
        )
    )
    assert len(cases) == 14
    assert all(item["passed"] is True for item in cases[:13])
    assert cases[-1]["caseId"] == "UAT-EMP-NL-314"
    assert cases[-1]["status"] == "success"
    assert cases[-1]["capabilityId"] == "employee.search"
    assert cases[-1]["fields"] == ["contact_address"]
    assert cases[-1]["operators"] == ["contains"]
    assert cases[-1]["employeeSearchCalls"] == 1
    assert cases[-1]["passed"] is False


def test_candidate_03_manifest_assets_are_recoverable_from_frozen_head() -> None:
    manifest_path = next(path for path in _FILES if path.endswith(".manifest.json"))
    manifest = cast(
        dict[str, object],
        json.loads((_ROOT / manifest_path).read_text(encoding="utf-8")),
    )
    assert len(cast(list[object], manifest["assets"])) == 45
    for raw in cast(list[object], manifest["assets"]):
        asset = cast(dict[str, str], raw)
        completed = subprocess.run(
            ["git", "show", f"{_FROZEN_HEAD}:{asset['path']}"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
        )
        assert hashlib.sha256(completed.stdout).hexdigest() == asset["sha256"]
