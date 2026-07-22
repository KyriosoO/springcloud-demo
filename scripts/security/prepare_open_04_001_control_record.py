#!/usr/bin/env python3
"""Prepare/finalize DR-04-045 records without reading or storing a private key."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "open-04-001-migration-approval-request-v0.1"
CONTROL_SCHEMA = "open-04-001-migration-control-v0.1"
SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")
REF_FIELDS = (
    "policyPayloadRef",
    "rollbackExercisePolicyPayloadRef",
    "trafficProfileRef",
    "thresholdsRef",
    "observationRunnerRef",
    "consumerScannerRef",
    "exitVerifierRef",
)


def canonical_bytes(value: Any) -> bytes:
    _reject_unsupported(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def prepare(spec: dict[str, Any], root: Path) -> dict[str, Any]:
    record = dict(spec)
    if "signature" in record or "sourceHashes" in record:
        raise ValueError("spec must not contain signature or sourceHashes")
    if record.get("schemaVersion") != CONTROL_SCHEMA:
        raise ValueError(f"schemaVersion must be {CONTROL_SCHEMA}")
    if record.get("environmentClass") != "NON_PRODUCTION_CONTROLLED":
        raise ValueError("environmentClass must be NON_PRODUCTION_CONTROLLED")
    if record.get("enabledModelTargetIds") != []:
        raise ValueError("enabledModelTargetIds must be empty")
    if record.get("runtimeToolTrafficEnabled") is not False or record.get("businessTrafficEnabled") is not False:
        raise ValueError("Runtime/Tool and business traffic flags must be false")
    if record.get("phaseSequence") != ["DUAL_READ_ENFORCE_INTERSECTION", "AGENT_FIELD_AUTHORITY"]:
        raise ValueError("phaseSequence must be exactly B then C")
    if record.get("operatorRefDigest") == record.get("approverRefDigest"):
        raise ValueError("operator and approver must be different")
    if record.get("policyVersion") == record.get("rollbackExercisePolicyVersion"):
        raise ValueError("primary and rollback-exercise policy versions must be distinct")
    primary = record.get("policyDigest")
    drill = record.get("rollbackExercisePolicyDigest")
    expected_operations = [
        {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": None, "toPolicyDigest": primary,
         "changeClass": "INITIAL", "expectedStateVersion": 0},
        {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": primary, "toPolicyDigest": drill,
         "changeClass": "TIGHTENING", "expectedStateVersion": 1},
        {"operation": "ROLLBACK", "fromPolicyDigest": drill, "toPolicyDigest": primary,
         "changeClass": "EXPANSION", "expectedStateVersion": 2},
    ]
    if not isinstance(primary, str) or not isinstance(drill, str) or primary == drill:
        raise ValueError("primary and rollback-exercise policy digests must be distinct")
    if record.get("policyOperations") != expected_operations:
        raise ValueError("policyOperations must be the exact INITIAL/TIGHTENING/ROLLBACK sequence")

    hashes: dict[str, str] = {}
    for field in REF_FIELDS:
        ref = record.get(field)
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"{field} must be a repository-relative path")
        source = _resolve(root, ref)
        if not source.is_file():
            raise ValueError(f"{field} does not exist: {ref}")
        hashes[ref] = hashlib.sha256(source.read_bytes()).hexdigest()
    record["sourceHashes"] = dict(sorted(hashes.items()))
    if record.get("policyDigest") != hashes[record["policyPayloadRef"]]:
        raise ValueError("policyDigest must match the canonical policy payload bytes")
    if record.get("rollbackExercisePolicyDigest") != hashes[record["rollbackExercisePolicyPayloadRef"]]:
        raise ValueError("rollbackExercisePolicyDigest must match the canonical drill policy payload bytes")
    if record.get("trafficProfileDigest") != hashes[record["trafficProfileRef"]]:
        raise ValueError("trafficProfileDigest does not match trafficProfileRef")
    if record.get("thresholdsDigest") != hashes[record["thresholdsRef"]]:
        raise ValueError("thresholdsDigest does not match thresholdsRef")
    payload = canonical_bytes(record)
    return {
        "schemaVersion": REQUEST_SCHEMA,
        "controlRecordWithoutSignature": record,
        "canonicalPayloadBase64": base64.b64encode(payload).decode("ascii"),
        "canonicalPayloadSha256": hashlib.sha256(payload).hexdigest(),
        "signingInstruction": "Sign the decoded canonicalPayloadBase64 bytes with the independent approver Ed25519 key; return only the 86-character Base64URL signature.",
    }


def finalize(request: dict[str, Any], signature: str) -> dict[str, Any]:
    if request.get("schemaVersion") != REQUEST_SCHEMA:
        raise ValueError("unsupported approval request schema")
    record = request.get("controlRecordWithoutSignature")
    if not isinstance(record, dict) or "signature" in record:
        raise ValueError("controlRecordWithoutSignature must be an unsigned object")
    payload = canonical_bytes(record)
    if base64.b64encode(payload).decode("ascii") != request.get("canonicalPayloadBase64"):
        raise ValueError("approval request canonical payload drifted")
    if hashlib.sha256(payload).hexdigest() != request.get("canonicalPayloadSha256"):
        raise ValueError("approval request digest drifted")
    signature = signature.strip()
    if SIGNATURE.fullmatch(signature) is None:
        raise ValueError("signature must be an 86-character Base64URL Ed25519 signature")
    return {**record, "signature": signature}


def _resolve(root: Path, relative: str) -> Path:
    if "\\" in relative or Path(relative).is_absolute():
        raise ValueError("source reference must use canonical repository-relative '/' paths")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("source reference escapes repository root") from exc
    return resolved


def _reject_unsupported(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, list):
        for item in value:
            _reject_unsupported(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _reject_unsupported(item)
        return
    raise ValueError("control record supports only objects, arrays, strings, booleans, integers and null")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--spec", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--root", type=Path, default=Path.cwd())
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--request", type=Path, required=True)
    finalize_parser.add_argument("--signature-file", type=Path, required=True)
    finalize_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            value = prepare(json.loads(args.spec.read_text(encoding="utf-8")), args.root)
        else:
            value = finalize(
                json.loads(args.request.read_text(encoding="utf-8")),
                args.signature_file.read_text(encoding="ascii"),
            )
        args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"OPEN-04-001 CONTROL RECORD BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
