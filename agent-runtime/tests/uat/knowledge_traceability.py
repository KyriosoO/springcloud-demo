from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, cast


_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_TRACEABILITY: Final[Path] = Path(__file__).with_name(
    "knowledge_uat_traceability.v2.json"
)
_LATEST_VALID_RESULT: Final[str] = (
    "agent-runtime/tests/evaluation/knowledge/results/"
    "knowledge-p5-live-v2-20260826-candidate-05/result.json"
)
_LATEST_VALID_RESULT_SHA256: Final[str] = (
    "a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb"
)
_LATEST_EXECUTION_MANIFEST: Final[str] = (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.manifest.json"
)
_LATEST_EXECUTION_MANIFEST_SHA256: Final[str] = (
    "af545166b37a33899d6f1d7830c09472df8cc2fe45047fea242ecc524bfc2211"
)
_LATEST_EXECUTION_AUTHORIZATION: Final[str] = (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.authorization.json"
)
_LATEST_EXECUTION_AUTHORIZATION_SHA256: Final[str] = (
    "47575441f1c9123facc19ad32210375cb919174c0260c6fc0e612740abf07a06"
)
_LATEST_EXECUTION_FAILURE: Final[str] = (
    "agent-runtime/tests/evaluation/knowledge/results/"
    "knowledge-p5-live-v4-20260828-candidate-07/preflight-failure.json"
)
_LATEST_EXECUTION_FAILURE_SHA256: Final[str] = (
    "919fa1480b2ad3c7144559a3f10746ded7e0d069beae0977e0a7222e771d32d6"
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
        "effectiveness",
        "cases",
    }:
        raise ValueError("knowledge_uat_traceability.shape_invalid")
    if (
        value["schemaVersion"] != 2
        or value["suiteId"] != "single-agent-knowledge-functional-uat-v2"
        or value["authority"] != "UAT_01 v1.21"
        or value["functionalConclusion"] != "passed"
    ):
        raise ValueError("knowledge_uat_traceability.identity_invalid")

    _validate_effectiveness(value["effectiveness"])

    cases = value["cases"]
    if type(cases) is not list or len(cases) != len(_EXPECTED_CASES):
        raise ValueError("knowledge_uat_traceability.cases_invalid")
    seen: set[str] = set()
    for item in cases:
        _validate_case(item, seen)
    if frozenset(seen) != _EXPECTED_CASES:
        raise ValueError("knowledge_uat_traceability.cases_invalid")

    _reject_forbidden_keys(value)


def _validate_effectiveness(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "latestValid",
        "latestExecution",
        "currentVersion",
    }:
        raise ValueError("knowledge_uat_traceability.effectiveness_shape_invalid")

    latest_valid = value["latestValid"]
    expected_latest_valid: dict[str, object] = {
        "runId": "knowledge-p5-live-v2-20260826-candidate-05",
        "summaryTaskVersion": "3",
        "conclusion": "partially_effective",
        "q1": True,
        "q2": True,
        "q3": False,
        "q4": False,
        "safetyGatePassed": True,
        "result": {
            "path": _LATEST_VALID_RESULT,
            "sha256": _LATEST_VALID_RESULT_SHA256,
        },
    }
    if latest_valid != expected_latest_valid:
        raise ValueError("knowledge_uat_traceability.latest_valid_invalid")

    latest_execution = value["latestExecution"]
    expected_latest_execution: dict[str, object] = {
        "runId": "knowledge-p5-live-v4-20260828-candidate-07",
        "summaryTaskVersion": "4",
        "conclusion": "invalid_run",
        "state": "failed_unconsumed",
        "modelCalls": 0,
        "paidRequests": 0,
        "businessCalls": 0,
        "retry": 0,
        "resume": 0,
        "manifest": {
            "path": _LATEST_EXECUTION_MANIFEST,
            "sha256": _LATEST_EXECUTION_MANIFEST_SHA256,
        },
        "authorization": {
            "path": _LATEST_EXECUTION_AUTHORIZATION,
            "sha256": _LATEST_EXECUTION_AUTHORIZATION_SHA256,
        },
        "failure": {
            "path": _LATEST_EXECUTION_FAILURE,
            "sha256": _LATEST_EXECUTION_FAILURE_SHA256,
        },
    }
    if latest_execution != expected_latest_execution:
        raise ValueError("knowledge_uat_traceability.latest_execution_invalid")

    if value["currentVersion"] != {
        "summaryTaskVersion": "4",
        "evidenceStatus": "missing",
    }:
        raise ValueError("knowledge_uat_traceability.current_version_invalid")

    result = _load_bound_json(_LATEST_VALID_RESULT, _LATEST_VALID_RESULT_SHA256)
    result_metrics = result.get("aggregateMetrics")
    result_safety = result.get("safetyGate")
    result_tasks = result.get("modelTaskVersions")
    if (
        result.get("runId") != "knowledge-p5-live-v2-20260826-candidate-05"
        or result.get("conclusion") != "partially_effective"
        or type(result_metrics) is not dict
        or {
            "q1": result_metrics.get("q1"),
            "q2": result_metrics.get("q2"),
            "q3": result_metrics.get("q3"),
            "q4": result_metrics.get("q4"),
        }
        != {"q1": True, "q2": True, "q3": False, "q4": False}
        or type(result_safety) is not dict
        or result_safety.get("passed") is not True
        or type(result_tasks) is not dict
        or result_tasks.get("knowledge_summary") != "3"
    ):
        raise ValueError("knowledge_uat_traceability.latest_valid_evidence_invalid")

    manifest = _load_bound_json(
        _LATEST_EXECUTION_MANIFEST, _LATEST_EXECUTION_MANIFEST_SHA256
    )
    manifest_tasks = manifest.get("taskVersions")
    authorization = _load_bound_json(
        _LATEST_EXECUTION_AUTHORIZATION, _LATEST_EXECUTION_AUTHORIZATION_SHA256
    )
    failure = _load_bound_json(
        _LATEST_EXECUTION_FAILURE, _LATEST_EXECUTION_FAILURE_SHA256
    )
    failure_counts = failure.get("counts")
    if (
        manifest.get("runId") != "knowledge-p5-live-v4-20260828-candidate-07"
        or type(manifest_tasks) is not dict
        or manifest_tasks.get("knowledge_summary") != "4"
        or authorization.get("runId") != manifest.get("runId")
        or failure.get("runId") != manifest.get("runId")
        or failure.get("status") != "failed_unconsumed"
        or type(failure_counts) is not dict
        or {
            key: failure_counts.get(key)
            for key in ("modelOutbound", "paidRequests", "businessCalls", "retry", "resume")
        }
        != {
            "modelOutbound": 0,
            "paidRequests": 0,
            "businessCalls": 0,
            "retry": 0,
            "resume": 0,
        }
    ):
        raise ValueError("knowledge_uat_traceability.latest_execution_evidence_invalid")


def _load_bound_json(relative: str, expected_sha256: str) -> dict[str, object]:
    path = _repository_path(relative)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("knowledge_uat_traceability.evidence_hash_invalid")
    value = json.loads(payload)
    if type(value) is not dict:
        raise ValueError("knowledge_uat_traceability.evidence_shape_invalid")
    return cast(dict[str, object], value)


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
