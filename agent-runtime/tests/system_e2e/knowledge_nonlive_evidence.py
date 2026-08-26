from __future__ import annotations

import json
import os
from pathlib import Path


EXPECTED_CASE_IDS = frozenset({
    "k-nonlive-policy-admin",
    "k-nonlive-law-viewer",
    "k-nonlive-multi-domain",
    "k-nonlive-rewrite-fallback",
    "k-nonlive-no-result",
    "k-nonlive-read-denied",
    "k-nonlive-partial-path",
    "k-nonlive-all-paths-fail",
    "k-nonlive-policy-missing",
    "k-nonlive-invalid-ref",
    "k-nonlive-duplicate-ref",
    "k-nonlive-summary-failure",
    "k-nonlive-sensitive",
    "k-nonlive-second-action",
})

_TOP_LEVEL = {
    "schemaVersion",
    "workPackage",
    "status",
    "cases",
    "totals",
    "security",
    "cleanup",
}
_CASE_KEYS = {"caseId", "status", "capabilityId", "failureCode", "calls"}
_CALL_KEYS = {"action", "rewrite", "summary", "businessModel", "embed", "search", "rerank"}
_TOTAL_KEYS = _CALL_KEYS | {"externalModelOutbound"}


def validate_knowledge_nonlive_evidence(value: object) -> None:
    if type(value) is not dict or set(value) != _TOP_LEVEL:
        raise ValueError("knowledge_nonlive.evidence_shape_invalid")
    if (
        value["schemaVersion"] != 1
        or value["workPackage"] != "WP-K-SPRING-NONLIVE-E2E-03"
        or value["status"] not in {"passed", "failed"}
        or type(value["cases"]) is not list
        or type(value["totals"]) is not dict
        or set(value["totals"]) != _TOTAL_KEYS
        or type(value["security"]) is not dict
        or value["security"] != {"sensitivePersistence": False, "logLeakCount": 0}
        or type(value["cleanup"]) is not dict
        or set(value["cleanup"]) != {"runtimeClosed", "knowledgeClientsClosed"}
        or any(type(item) is not int or item < 0 for item in value["totals"].values())
    ):
        raise ValueError("knowledge_nonlive.evidence_shape_invalid")
    case_ids: list[str] = []
    for item in value["cases"]:
        if (
            type(item) is not dict
            or set(item) != _CASE_KEYS
            or type(item["caseId"]) is not str
            or item["status"] not in {
                "success", "no_result", "forbidden", "model_egress_denied",
                "invalid_argument", "downstream_failure", "timeout", "unsupported",
            }
            or item["capabilityId"] not in {None, "knowledge.query"}
            or item["failureCode"] is not None and type(item["failureCode"]) is not str
            or type(item["calls"]) is not dict
            or set(item["calls"]) != _CALL_KEYS
            or any(type(count) is not int or count < 0 for count in item["calls"].values())
        ):
            raise ValueError("knowledge_nonlive.evidence_shape_invalid")
        case_ids.append(item["caseId"])
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("knowledge_nonlive.evidence_shape_invalid")
    if value["status"] == "passed" and (
        set(case_ids) != EXPECTED_CASE_IDS
        or value["totals"]["externalModelOutbound"] != 0
        or value["totals"]["businessModel"] != 0
        or not value["cleanup"]["runtimeClosed"]
        or not value["cleanup"]["knowledgeClientsClosed"]
    ):
        raise ValueError("knowledge_nonlive.evidence_false_pass")


def write_knowledge_nonlive_evidence(
    path: Path,
    *,
    cases: tuple[dict[str, object], ...],
    totals: dict[str, int],
    runtime_closed: bool,
    clients_closed: bool,
) -> None:
    value: dict[str, object] = {
        "schemaVersion": 1,
        "workPackage": "WP-K-SPRING-NONLIVE-E2E-03",
        "status": "passed" if {item["caseId"] for item in cases} == EXPECTED_CASE_IDS else "failed",
        "cases": list(cases),
        "totals": {**totals, "externalModelOutbound": 0},
        "security": {"sensitivePersistence": False, "logLeakCount": 0},
        "cleanup": {
            "runtimeClosed": runtime_closed,
            "knowledgeClientsClosed": clients_closed,
        },
    }
    validate_knowledge_nonlive_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, path)
