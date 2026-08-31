from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast


_ROOT = Path(__file__).resolve().parents[4]
_FROZEN_HEAD = "0fef025815c210a8ea3bfc2e64ed7451bee829ad"
_RUN_ID = "employee-natural-language-v1-20260828-candidate-04"
_MANIFEST_SHA256 = "e6c908503aa4f9544c6fea6e32e072ac76708ef6401cc46d32b61c513fefb19c"
_FILES = {
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-04.manifest.json": _MANIFEST_SHA256,
    "agent-runtime/tests/uat/employee_nl/evidence/employee-natural-language-v1-20260828-candidate-04.authorization.json": "e2f44d3b56f647b81c65b306f808d24687f120cc36f0a6e6e35d95ef3c64bea4",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/authorization.consumed.json": "851e7fe4ca4c1fb5b20b0ccc1989bff0f3b7acde1b0dbdc8dd0c9a7aaeec42e1",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/attempts.jsonl": "94aaaa5c2e11e28639ec547f5dafe3fc0844a528d68a216db291191570386ddf",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/lifecycle.jsonl": "89a162c68e0170fd93a1ee93bc3db59f538a83857e89595b714f1800b6f0fa36",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/result.json": "2dc6e4c3755f2a32542e6219d671b388a9b1eb7dc97c510225d995a5d3cc48fd",
    "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/launcher-evidence.json": "4370510ddd90e960e10c0b6d333bc679a0f4a38fcf96d47ea5422288ebc3d6b5",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_04_consumed_success_assets_are_immutable() -> None:
    for relative, expected in _FILES.items():
        assert _sha256(_ROOT / relative) == expected

    result_path = next(path for path in _FILES if path.endswith("/result.json"))
    result = cast(
        dict[str, object],
        json.loads((_ROOT / result_path).read_text(encoding="utf-8")),
    )
    counts = cast(dict[str, object], result["counts"])
    security = cast(dict[str, object], result["security"])
    cleanup = cast(dict[str, object], result["cleanup"])
    cases = cast(list[dict[str, object]], result["cases"])
    assert result["status"] == "passed"
    assert result["runId"] == _RUN_ID
    assert result["frozenHead"] == _FROZEN_HEAD
    assert result["manifestSha256"] == _MANIFEST_SHA256
    assert counts["modelCalls"] == 12
    assert counts["employeeSearchCalls"] == 11
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
    assert security == {
        "forbiddenPersistence": 0,
        "forbiddenPlanValues": 0,
        "logLeakCount": 0,
    }
    assert set(cleanup.values()) == {True}
    assert len(cases) == 13
    assert all(item["passed"] is True for item in cases)

    unsupported = next(item for item in cases if item["caseId"] == "UAT-EMP-NL-314")
    assert unsupported["status"] == "unsupported"
    assert unsupported["capabilityId"] is None
    assert unsupported["employeeSearchCalls"] == 0
    assert unsupported["failureCode"] == "business.plan_unsupported"

    pre_model = next(item for item in cases if item["caseId"] == "UAT-EMP-NL-315")
    assert pre_model["status"] == "invalid_argument"
    assert pre_model["modelCalls"] == 0
    assert pre_model["employeeSearchCalls"] == 0


def test_candidate_04_manifest_assets_are_recoverable_from_frozen_head() -> None:
    manifest_path = next(path for path in _FILES if path.endswith(".manifest.json"))
    manifest = cast(
        dict[str, object],
        json.loads((_ROOT / manifest_path).read_text(encoding="utf-8")),
    )
    assert len(cast(list[object], manifest["assets"])) == 59
    for raw in cast(list[object], manifest["assets"]):
        asset = cast(dict[str, str], raw)
        completed = subprocess.run(
            ["git", "show", f"{_FROZEN_HEAD}:{asset['path']}"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
        )
        assert hashlib.sha256(completed.stdout).hexdigest() == asset["sha256"]


def test_candidate_03_and_04_cover_all_fifteen_uat_categories_within_budget() -> None:
    candidate_03 = cast(
        dict[str, object],
        json.loads(
            (
                _ROOT
                / "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-03/result.json"
            ).read_text(encoding="utf-8")
        ),
    )
    candidate_04 = cast(
        dict[str, object],
        json.loads(
            (
                _ROOT
                / "agent-runtime/tests/uat/employee_nl/results/employee-natural-language-v1-20260828-candidate-04/result.json"
            ).read_text(encoding="utf-8")
        ),
    )
    candidate_03_cases = {
        cast(str, item["caseId"]): item
        for item in cast(list[dict[str, object]], candidate_03["cases"])
    }
    candidate_04_cases = {
        cast(str, item["caseId"]): item
        for item in cast(list[dict[str, object]], candidate_04["cases"])
    }
    selected = dict(candidate_04_cases)
    selected["UAT-EMP-NL-302"] = candidate_03_cases["UAT-EMP-NL-302"]
    selected["UAT-EMP-NL-307"] = candidate_03_cases["UAT-EMP-NL-307"]

    assert set(selected) == {f"UAT-EMP-NL-{number}" for number in range(301, 316)}
    assert all(item["passed"] is True for item in selected.values())

    totals = {"modelCalls": 0, "employeeSearchCalls": 0}
    for candidate in range(1, 5):
        result = cast(
            dict[str, object],
            json.loads(
                (
                    _ROOT
                    / (
                        "agent-runtime/tests/uat/employee_nl/results/"
                        f"employee-natural-language-v1-20260828-candidate-0{candidate}/result.json"
                    )
                ).read_text(encoding="utf-8")
            ),
        )
        counts = cast(dict[str, int], result["counts"])
        totals["modelCalls"] += counts["modelCalls"]
        totals["employeeSearchCalls"] += counts["employeeSearchCalls"]
    assert totals == {"modelCalls": 30, "employeeSearchCalls": 27}
