#!/usr/bin/env python3
"""Deterministic B/C observation over every current Auth permission profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "open-04-001-controlled-observation-v0.1"
TRAFFIC_SCHEMA = "open-04-001-traffic-profile-v0.1"
THRESHOLDS_SCHEMA = "open-04-001-thresholds-v0.1"
RULE_MAP = {
    "filterable-fields": "filterableFields",
    "displayable-fields": "displayableFields",
    "allowed-operators": "allowedOperators",
    "allowed-functions": "allowedFunctions",
}
NEGATIVE_CASES = {
    "UNKNOWN_PERMISSION_CODE", "MISSING_LEGACY", "UNMAPPABLE", "EXPIRED_AUTH", "STATE_VERSION_CONFLICT"
}


def run(auth_path: Path, seed_path: Path, traffic_path: Path, thresholds_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    auth_root = yaml.safe_load(auth_path.read_text(encoding="utf-8"))
    seed_root = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    traffic = json.loads(traffic_path.read_text(encoding="utf-8"))
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    if traffic.get("schemaVersion") != TRAFFIC_SCHEMA or thresholds.get("schemaVersion") != THRESHOLDS_SCHEMA:
        raise ValueError("unsupported traffic or thresholds schema")
    iterations = traffic.get("iterationsPerProfilePerPhase")
    minimum = thresholds.get("minimumPerProfilePerPhase")
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < minimum or minimum < 100:
        raise ValueError("each profile must execute at least 100 resolutions per phase")

    rbac = auth_root["auth"]["rbac"]
    auth_profiles = rbac["permission-profiles"]
    seed_profiles = seed_root["field-policies"]
    role_mappings: dict[str, str] = {}
    for role in rbac["roles"].values():
        profile = role["permission-profile"]
        for code in role["permission-codes"]:
            previous = role_mappings.setdefault(str(code), str(profile))
            if previous != profile:
                raise ValueError("permission code maps to multiple Auth profiles")
    declared_codes = traffic.get("permissionCodes")
    if not isinstance(declared_codes, list) or set(declared_codes) != set(role_mappings):
        raise ValueError("traffic profile must cover every known permission code exactly")
    if set(seed_profiles) != set(role_mappings):
        raise ValueError("Agent seed must cover every known permission code exactly")

    profiles = []
    totals = {"EQUAL": 0, "AUTH_WIDER_THAN_AGENT": 0, "AGENT_WIDER_THAN_AUTH": 0, "UNMAPPABLE": 0}
    for code in sorted(role_mappings):
        auth_view = _normalize(auth_profiles[role_mappings[code]])
        agent_views = {code: _normalize(seed_profiles[code])}
        phase_b = [_resolve([code], agent_views, auth_view, "B") for _ in range(iterations)]
        phase_c = [_resolve([code], agent_views, auth_view, "C") for _ in range(iterations)]
        diff = phase_b[0][0]
        if any(value[0] != diff for value in phase_b + phase_c):
            raise ValueError("deterministic profile resolution drifted")
        totals[diff] += len(phase_b) + len(phase_c)
        profiles.append({
            "permissionCode": code,
            "authProfileId": role_mappings[code],
            "phaseB": {"resolutionCount": len(phase_b), "diff": diff,
                       "legacyDecisionReadCount": sum(1 for _, used in phase_b if used)},
            "phaseC": {"resolutionCount": len(phase_c), "diff": diff,
                       "legacyDecisionReadCount": sum(1 for _, used in phase_c if used)},
        })

    declared_negative = traffic.get("negativeCases")
    if not isinstance(declared_negative, list) or set(declared_negative) != NEGATIVE_CASES:
        raise ValueError("traffic profile must declare all five fixed negative cases")
    first_code = sorted(seed_profiles)[0]
    first_view = _normalize(seed_profiles[first_code])
    negative_checks = {
        "UNKNOWN_PERMISSION_CODE": lambda: _expect_rejection(
            lambda: _resolve(["unknown-permission-code"], {first_code: first_view}, first_view, "C")),
        "MISSING_LEGACY": lambda: _expect_rejection(
            lambda: _resolve([first_code], {first_code: first_view}, None, "B")),
        "UNMAPPABLE": lambda: _expect_rejection(
            lambda: _resolve([first_code], {first_code: first_view}, _disjoint_view(), "B")),
        "EXPIRED_AUTH": lambda: _expect_rejection(lambda: _require_not_expired(100, 100)),
        "STATE_VERSION_CONFLICT": lambda: _expect_rejection(lambda: _require_state_version(1, 2)),
    }
    negative_results = []
    for name in sorted(NEGATIVE_CASES):
        rejected = negative_checks[name]()
        negative_results.append({"case": name, "attemptCount": 1, "rejectedCount": int(rejected)})
    passed = (
        totals["AGENT_WIDER_THAN_AUTH"] == 0
        and totals["UNMAPPABLE"] == 0
        and all(item["phaseC"]["legacyDecisionReadCount"] == 0 for item in profiles)
        and all(item["rejectedCount"] == item["attemptCount"] for item in negative_results)
    )
    observation = {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceDigests": {
            str(auth_path).replace("\\", "/"): _sha(auth_path),
            str(seed_path).replace("\\", "/"): _sha(seed_path),
            str(traffic_path).replace("\\", "/"): _sha(traffic_path),
            str(thresholds_path).replace("\\", "/"): _sha(thresholds_path),
        },
        "profiles": profiles,
        "totals": totals,
        "legacyDecisionReadCount": sum(item["phaseC"]["legacyDecisionReadCount"] for item in profiles),
        "negativeCases": negative_results,
        "thresholdsPassed": passed,
    }
    if not passed:
        raise ValueError("controlled observation thresholds were not satisfied")
    policy_payload = {"fieldPolicies": {code: _normalize(seed_profiles[code]) for code in sorted(seed_profiles)}}
    return observation, policy_payload


def _normalize(profile: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for source, target in RULE_MAP.items():
        raw = profile.get(source) or {}
        result[target] = {str(key): sorted({str(value) for value in values}) for key, values in sorted(raw.items())}
    return result


def _compare(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_set = _flatten(left)
    right_set = _flatten(right)
    if left_set == right_set:
        return "EQUAL"
    if right_set <= left_set:
        return "AUTH_WIDER_THAN_AGENT"
    if left_set <= right_set:
        return "AGENT_WIDER_THAN_AUTH"
    return "UNMAPPABLE"


def _resolve(permission_codes, agent_views, legacy_view, phase):
    if any(code not in agent_views for code in permission_codes):
        raise ValueError("SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE")
    agent_set: set[tuple[str, str, str]] = set()
    for code in permission_codes:
        agent_set.update(_flatten(agent_views[code]))
    agent_view = _from_flattened(agent_set)
    if phase == "B":
        if legacy_view is None:
            raise ValueError("legacy field view is required in phase B")
        diff = _compare(legacy_view, agent_view)
        if diff == "UNMAPPABLE":
            raise ValueError("SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE")
        return diff, True
    if phase == "C":
        return (_compare(legacy_view, agent_view) if legacy_view is not None else "UNOBSERVED"), False
    raise ValueError("unsupported phase")


def _from_flattened(values):
    result = {target: {} for target in RULE_MAP.values()}
    for rule, key, value in sorted(values):
        result[rule].setdefault(key, []).append(value)
    return result


def _disjoint_view():
    return {
        "filterableFields": {"unrelated": ["field"]},
        "displayableFields": {}, "allowedOperators": {}, "allowedFunctions": {},
    }


def _require_not_expired(now, valid_until):
    if now >= valid_until:
        raise ValueError("AUTH_FACT_EXPIRED")


def _require_state_version(expected, actual):
    if expected != actual:
        raise ValueError("SECURITY_POLICY_CONFLICT")


def _expect_rejection(operation):
    try:
        operation()
    except ValueError:
        return True
    return False


def build_tightening_drill_policy(policy_payload: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(policy_payload))
    policies = result.get("fieldPolicies")
    if not isinstance(policies, dict):
        raise ValueError("policy payload has no fieldPolicies")
    for code in sorted(policies):
        rules = policies[code]
        for rule in ("displayableFields", "filterableFields", "allowedOperators", "allowedFunctions"):
            mapping = rules.get(rule)
            if not isinstance(mapping, dict):
                continue
            for key in sorted(mapping):
                values = mapping[key]
                if isinstance(values, list) and len(values) > 1:
                    mapping[key] = values[:-1]
                    return result
    raise ValueError("policy payload has no safely removable grant for rollback drill")


def _flatten(view: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {(rule, key, value) for rule, mapping in view.items() for key, values in mapping.items() for value in values}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--traffic", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy-output", type=Path, required=True)
    parser.add_argument("--rollback-policy-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        observation, policy = run(args.auth, args.seed, args.traffic, args.thresholds)
        args.output.write_text(json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.policy_output.write_text(
            json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        args.rollback_policy_output.write_text(
            json.dumps(build_tightening_drill_policy(policy), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"OPEN-04-001 OBSERVATION BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
