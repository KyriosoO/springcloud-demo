from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, cast


_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_TRACEABILITY: Final[Path] = Path(__file__).with_name("uat_traceability.v2.json")
_EXPECTED_CASES: Final[dict[str, frozenset[str]]] = {
    "public": frozenset(f"UAT-PUB-{value}" for value in range(201, 206)),
    "employee": frozenset(f"UAT-EMP-{value}" for value in range(201, 216)),
    "transaction": frozenset(f"UAT-TXN-{value}" for value in range(201, 216)),
}
_REAL_RESULT: Final[str] = (
    "agent-runtime/tests/system_e2e/live/results/business-list-v2-uat-run03.result.json"
)
_FORBIDDEN_CURRENT_MARKERS: Final[tuple[str, ...]] = (
    "employee.detail",
    "single-agent-structured-query-uat-v1",
    "AgentStructuredQueryUATTest",
)


def load_current_uat_traceability() -> dict[str, object]:
    value = json.loads(_TRACEABILITY.read_bytes())
    validate_current_uat_traceability(value)
    return cast(dict[str, object], value)


def validate_current_uat_traceability(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "schemaVersion", "suiteId", "authority", "historicalRealEvidence", "cases"
    }:
        raise ValueError("uat_traceability.shape_invalid")
    if (
        value["schemaVersion"] != 2
        or value["suiteId"] != "single-agent-business-query-uat-v2"
        or value["authority"] != "UAT_00 v1.14"
    ):
        raise ValueError("uat_traceability.identity_invalid")

    historical = value["historicalRealEvidence"]
    if type(historical) is not dict or set(historical) != {"path", "sha256", "caseCount"}:
        raise ValueError("uat_traceability.history_invalid")
    if historical["path"] != _REAL_RESULT or historical["caseCount"] != 18:
        raise ValueError("uat_traceability.history_invalid")
    real_path = _repository_path(str(historical["path"]))
    if hashlib.sha256(real_path.read_bytes()).hexdigest() != historical["sha256"]:
        raise ValueError("uat_traceability.history_hash_invalid")
    real_value = json.loads(real_path.read_bytes())
    if type(real_value) is not dict or type(real_value.get("cases")) is not list:
        raise ValueError("uat_traceability.history_invalid")
    real_case_ids = {
        item.get("caseId") for item in real_value["cases"] if type(item) is dict
    }
    if len(real_case_ids) != 18:
        raise ValueError("uat_traceability.history_invalid")

    cases = value["cases"]
    if type(cases) is not list or len(cases) != 35:
        raise ValueError("uat_traceability.cases_invalid")
    seen: dict[str, set[str]] = {stage: set() for stage in _EXPECTED_CASES}
    real_count = 0
    for item in cases:
        _validate_case(item, seen=seen, real_case_ids=real_case_ids)
        if item["hasRealLlmEvidence"] is True:
            real_count += 1
    if {stage: frozenset(case_ids) for stage, case_ids in seen.items()} != _EXPECTED_CASES:
        raise ValueError("uat_traceability.cases_invalid")
    if real_count != 18:
        raise ValueError("uat_traceability.real_count_invalid")
    material = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if any(marker in material for marker in _FORBIDDEN_CURRENT_MARKERS):
        raise ValueError("uat_traceability.historical_path_exposed")


def _validate_case(
    item: object,
    *,
    seen: dict[str, set[str]],
    real_case_ids: set[object],
) -> None:
    required = {
        "caseId", "stage", "status", "verificationKind", "hasRealLlmEvidence",
        "evidenceRefs", "riskClosure",
    }
    if type(item) is not dict or set(item) != required:
        raise ValueError("uat_traceability.case_shape_invalid")
    case_id = item["caseId"]
    stage = item["stage"]
    if (
        type(case_id) is not str
        or stage not in _EXPECTED_CASES
        or case_id not in _EXPECTED_CASES[str(stage)]
        or case_id in seen[str(stage)]
        or item["status"] != "passed"
        or type(item["verificationKind"]) is not str
        or not item["verificationKind"]
        or type(item["hasRealLlmEvidence"]) is not bool
        or type(item["riskClosure"]) is not str
        or not item["riskClosure"]
    ):
        raise ValueError("uat_traceability.case_invalid")
    seen[str(stage)].add(case_id)

    references = item["evidenceRefs"]
    if type(references) is not list or not references:
        raise ValueError("uat_traceability.references_invalid")
    has_real_reference = False
    for reference in references:
        if type(reference) is not dict or set(reference) != {"path", "symbol"}:
            raise ValueError("uat_traceability.references_invalid")
        path = reference["path"]
        symbol = reference["symbol"]
        if type(path) is not str or type(symbol) is not str or not symbol:
            raise ValueError("uat_traceability.references_invalid")
        evidence_path = _repository_path(path)
        if path == _REAL_RESULT:
            has_real_reference = True
            if symbol != case_id:
                raise ValueError("uat_traceability.real_case_mismatch")
        elif symbol not in evidence_path.read_text(encoding="utf-8"):
            raise ValueError("uat_traceability.symbol_missing")
    has_real = item["hasRealLlmEvidence"]
    if has_real is not (case_id in real_case_ids) or has_real is not has_real_reference:
        raise ValueError("uat_traceability.real_case_mismatch")


def _repository_path(relative: str) -> Path:
    if not relative or "\\" in relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("uat_traceability.path_invalid")
    candidate = (_REPOSITORY_ROOT / relative).resolve()
    if _REPOSITORY_ROOT not in candidate.parents or not candidate.is_file():
        raise ValueError("uat_traceability.path_invalid")
    return candidate
