from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

_MATRIX = {
    "adminPrimary": "allowed",
    "adminSecondary": "allowed",
    "viewer": "allowed",
    "unknownRole": "forbidden",
    "missingToken": "unauthenticated",
    "malformedToken": "unauthenticated",
    "serviceToken": "unauthenticated",
}
_PROBE_COUNTS = {"transaction": 7, "adapter": 6, "otherTransactionEndpoints": 0, "model": 0}
_FINAL_COUNTS = {
    **_PROBE_COUNTS,
    "gateway": 1,
    "serviceSearch": 4,
    "mapperCountUpTo": 4,
    "mapperQuery": 0,
    "otherServiceMethods": 0,
}
_PRECISION = {
    "amountExact": True,
    "amountGtExact": True,
    "amountLtExact": True,
    "gatewayAmountExact": True,
    "jsonNumberOnly": True,
    "mapperValuesUnmodified": True,
}
_FINAL_KEYS = {
    "schemaVersion",
    "workPackage",
    "validations",
    "status",
    "startedAtUtc",
    "completedAtUtc",
    "durationMs",
    "authorizationMatrix",
    "precisionMatrix",
    "requestCounts",
    "responseVisibility",
    "logSafety",
    "runtimeIsolation",
}


def _invalid() -> NoReturn:
    raise ValueError("transaction.live_evidence_invalid")


def _exact_object(value: object, expected_keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected_keys:
        _invalid()
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _invalid()
    if parsed.tzinfo is None:
        _invalid()
    return parsed


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def load_strict_json(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if not raw or len(raw) > 16_384 or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if type(value) is not dict:
        _invalid()
    return value


def validate_probe_evidence(value: object) -> dict[str, object]:
    probe = _exact_object(
        value,
        {"schemaVersion", "authorizationMatrix", "precisionMatrix", "requestCounts", "responseVisibility"},
    )
    if probe["schemaVersion"] != 1 or probe["responseVisibility"] != "empty_response_with_provider_contract":
        _invalid()
    if _exact_object(probe["authorizationMatrix"], set(_MATRIX)) != _MATRIX:
        _invalid()
    if _exact_object(probe["precisionMatrix"], {"jsonNumberOnly"}) != {"jsonNumberOnly": True}:
        _invalid()
    if _exact_object(probe["requestCounts"], set(_PROBE_COUNTS)) != _PROBE_COUNTS:
        _invalid()
    return probe


def validate_final_evidence(value: object) -> dict[str, object]:
    evidence = _exact_object(value, _FINAL_KEYS)
    if (
        evidence["schemaVersion"] != 1
        or evidence["workPackage"] != "WP-TXN-REAL-01"
        or evidence["validations"] != ["VAL-TXN-004", "VAL-TXN-005"]
        or evidence["status"] != "passed"
        or evidence["responseVisibility"] != "provider_contract_and_empty_live_response"
    ):
        _invalid()
    started = _timestamp(evidence["startedAtUtc"])
    completed = _timestamp(evidence["completedAtUtc"])
    duration = evidence["durationMs"]
    if type(duration) is not int or duration < 0 or completed < started:
        _invalid()
    if _exact_object(evidence["authorizationMatrix"], set(_MATRIX)) != _MATRIX:
        _invalid()
    if _exact_object(evidence["precisionMatrix"], set(_PRECISION)) != _PRECISION:
        _invalid()
    if _exact_object(evidence["requestCounts"], set(_FINAL_COUNTS)) != _FINAL_COUNTS:
        _invalid()
    if _exact_object(
        evidence["logSafety"],
        {
            "logLeakCount",
            "rawLogsDeleted",
            "transactionValuePersisted",
            "jwtPersisted",
            "hmacKeyPersisted",
            "bodyPersisted",
            "principalPersisted",
        },
    ) != {
        "logLeakCount": 0,
        "rawLogsDeleted": True,
        "transactionValuePersisted": False,
        "jwtPersisted": False,
        "hmacKeyPersisted": False,
        "bodyPersisted": False,
        "principalPersisted": False,
    }:
        _invalid()
    if _exact_object(
        evidence["runtimeIsolation"],
        {
            "authService",
            "transactionService",
            "gatewayService",
            "databaseAccessed",
            "permanentRouteUsed",
            "deepSeekCalled",
        },
    ) != {
        "authService": "isolated_local",
        "transactionService": "spring_boot_test_netty",
        "gatewayService": "actual_jar_formal_mq_route",
        "databaseAccessed": False,
        "permanentRouteUsed": True,
        "deepSeekCalled": False,
    }:
        _invalid()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    validate_final_evidence(load_strict_json(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
