from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast


_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_TRACEABILITY: Final[Path] = Path(__file__).with_name(
    "knowledge_uat_traceability.v1.json"
)
_EXPECTED_CASES: Final[frozenset[str]] = frozenset(
    [f"UAT-K-PUB-{value:03d}" for value in range(1, 7)]
    + [f"UAT-K-RW-{value:03d}" for value in range(1, 5)]
    + [f"UAT-K-DOM-{value:03d}" for value in range(1, 6)]
    + [f"UAT-K-RET-{value:03d}" for value in range(1, 9)]
    + [f"UAT-K-EV-{value:03d}" for value in range(1, 9)]
    + [f"UAT-K-ISO-{value:03d}" for value in range(1, 7)]
)
_VALIDATION_MODES: Final[frozenset[str]] = frozenset(
    {"spring_runtime_nonlive", "python_nonlive", "java_contract"}
)
_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {"question", "token", "jwt", "content", "prompt", "modelResponse"}
)


def load_knowledge_uat_traceability() -> dict[str, object]:
    value = json.loads(_TRACEABILITY.read_bytes())
    validate_knowledge_uat_traceability(value)
    return cast(dict[str, object], value)


def validate_knowledge_uat_traceability(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "suiteId",
        "authority",
        "functionalConclusion",
        "effectivenessConclusion",
        "cases",
    }:
        raise ValueError("knowledge_uat_traceability.shape_invalid")
    if (
        value["schemaVersion"] != 1
        or value["suiteId"] != "single-agent-knowledge-functional-uat-v1"
        or value["authority"] != "UAT_01 v1.1"
        or value["functionalConclusion"] != "passed"
        or value["effectivenessConclusion"] != "ineffective_candidate_04"
    ):
        raise ValueError("knowledge_uat_traceability.identity_invalid")

    cases = value["cases"]
    if type(cases) is not list or len(cases) != len(_EXPECTED_CASES):
        raise ValueError("knowledge_uat_traceability.cases_invalid")
    seen: set[str] = set()
    for item in cases:
        _validate_case(item, seen)
    if frozenset(seen) != _EXPECTED_CASES:
        raise ValueError("knowledge_uat_traceability.cases_invalid")

    _reject_forbidden_keys(value)


def _validate_case(item: object, seen: set[str]) -> None:
    required = {
        "caseId",
        "risk",
        "validationMode",
        "evidenceRefs",
        "actualResult",
        "status",
    }
    if type(item) is not dict or set(item) != required:
        raise ValueError("knowledge_uat_traceability.case_shape_invalid")
    case_id = item["caseId"]
    if (
        type(case_id) is not str
        or case_id not in _EXPECTED_CASES
        or case_id in seen
        or item["validationMode"] not in _VALIDATION_MODES
        or item["status"] != "passed"
        or type(item["risk"]) is not str
        or not item["risk"]
        or type(item["actualResult"]) is not str
        or not item["actualResult"]
    ):
        raise ValueError("knowledge_uat_traceability.case_invalid")
    seen.add(case_id)

    references = item["evidenceRefs"]
    if type(references) is not list or not references:
        raise ValueError("knowledge_uat_traceability.references_invalid")
    for reference in references:
        if type(reference) is not dict or set(reference) != {"path", "symbol"}:
            raise ValueError("knowledge_uat_traceability.references_invalid")
        path = reference["path"]
        symbol = reference["symbol"]
        if type(path) is not str or type(symbol) is not str or not symbol:
            raise ValueError("knowledge_uat_traceability.references_invalid")
        evidence_path = _repository_path(path)
        if symbol not in evidence_path.read_text(encoding="utf-8"):
            raise ValueError("knowledge_uat_traceability.symbol_missing")


def _reject_forbidden_keys(value: object) -> None:
    if type(value) is dict:
        if _FORBIDDEN_KEYS.intersection(value):
            raise ValueError("knowledge_uat_traceability.sensitive_shape_invalid")
        for child in value.values():
            _reject_forbidden_keys(child)
    elif type(value) is list:
        for child in value:
            _reject_forbidden_keys(child)


def _repository_path(relative: str) -> Path:
    if not relative or "\\" in relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("knowledge_uat_traceability.path_invalid")
    candidate = (_REPOSITORY_ROOT / relative).resolve()
    if _REPOSITORY_ROOT not in candidate.parents or not candidate.is_file():
        raise ValueError("knowledge_uat_traceability.path_invalid")
    return candidate
