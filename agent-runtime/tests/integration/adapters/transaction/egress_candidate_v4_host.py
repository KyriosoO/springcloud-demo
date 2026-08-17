from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, NoReturn


RUN_ID: Final = "transaction-egress-v4-20260817-candidate-04"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-026"
HOST_SCHEMA_VERSION: Final = 1
_SHA256 = re.compile(r"[0-9a-f]{64}")
_JOURNAL_KEYS = {
    "schemaVersion",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "sequence",
    "event",
    "status",
    "reason",
}
_RESULT_KEYS = {
    "schemaVersion",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "status",
    "sourceValidated",
    "collectionValidated",
    "counts",
    "safety",
    "failure",
}
_FAILURE_REASONS = {
    None,
    "asset_hash_invalid",
    "manifest_binding_invalid",
    "python_import_failed",
    "python_import_source_invalid",
    "python_collection_failed",
    "preflight_internal_failure",
}


class TransactionEgressHostPreflightError(RuntimeError):
    pass


def _invalid() -> NoReturn:
    raise TransactionEgressHostPreflightError("transaction.egress_host_preflight_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def load_strict_json(path: Path, *, max_bytes: int = 65_536) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > max_bytes:
        _invalid()
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: _invalid(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid()
    if not isinstance(value, dict):
        _invalid()
    return value


def _json_line(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _append_fsync(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND)
    with os.fdopen(descriptor, "ab", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _record(
    path: Path,
    *,
    manifest_sha256: str,
    sequence: int,
    event: str,
    status: str,
    reason: str | None,
    exclusive: bool = False,
) -> None:
    value: dict[str, object] = {
        "schemaVersion": HOST_SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "sequence": sequence,
        "event": event,
        "status": status,
        "reason": reason,
    }
    payload = _json_line(value)
    if exclusive:
        _write_exclusive(path, payload)
    else:
        _append_fsync(path, payload)


def _safe_subprocess_environment() -> dict[str, str]:
    allowed = ("SystemRoot", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP")
    result = {name: os.environ[name] for name in allowed if name in os.environ}
    result["PYTHONIOENCODING"] = "utf-8"
    return result


def _collection_probe_code() -> str:
    return (
        "import pathlib,sys;"
        "source=pathlib.Path(sys.argv[1]).resolve();"
        "runtime=pathlib.Path(sys.argv[2]).resolve();"
        "test_path=pathlib.Path(sys.argv[3]).resolve();"
        "expected_source=pathlib.Path(sys.argv[4]).resolve();"
        "expected=(expected_source/'agent_runtime'/'__init__.py').resolve();"
        "sys.path.insert(0,str(runtime));"
        "sys.path.insert(0,str(source));"
        "import agent_runtime;"
        "actual=pathlib.Path(agent_runtime.__file__).resolve();"
        "actual==expected or sys.exit(23);"
        "import pytest;"
        "code=pytest.main([str(test_path),'--collect-only','-q','--disable-warnings']);"
        "raise SystemExit(0 if code==0 else 24)"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_manifest_assets(
    *, repository: Path, manifest_path: Path, manifest_sha256: str
) -> None:
    try:
        manifest = load_strict_json(manifest_path, max_bytes=262_144)
        actual_manifest_sha256 = _sha256_file(manifest_path)
    except (OSError, TransactionEgressHostPreflightError) as error:
        raise TransactionEgressHostPreflightError("manifest_binding_invalid") from error
    if (
        actual_manifest_sha256 != manifest_sha256
        or manifest.get("runId") != RUN_ID
        or manifest.get("authorizationReference") != AUTHORIZATION_REFERENCE
        or manifest.get("status") != "prepared_unconsumed"
    ):
        raise TransactionEgressHostPreflightError("manifest_binding_invalid")
    collections = (manifest.get("history"), manifest.get("assetHashes"))
    for collection in collections:
        if not isinstance(collection, list) or not collection:
            raise TransactionEgressHostPreflightError("manifest_binding_invalid")
        for item in collection:
            if (
                not isinstance(item, Mapping)
                or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str)
                or not isinstance(item["sha256"], str)
                or _SHA256.fullmatch(item["sha256"]) is None
            ):
                raise TransactionEgressHostPreflightError("manifest_binding_invalid")
            try:
                path = (repository / item["path"]).resolve()
                valid = (
                    repository in path.parents
                    and path.is_file()
                    and _sha256_file(path) == item["sha256"]
                )
            except OSError:
                valid = False
            if not valid:
                raise TransactionEgressHostPreflightError("asset_hash_invalid")


def execute_import_preflight(
    *,
    repository_root: Path,
    journal_path: Path,
    result_path: Path,
    manifest_sha256: str,
    manifest_path: Path | None = None,
    python_executable: Path | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    if not _SHA256.fullmatch(manifest_sha256):
        _invalid()
    repository = repository_root.resolve()
    source = (source_root or repository / "agent-runtime" / "src").resolve()
    runtime = (repository / "agent-runtime").resolve()
    live_test = (
        runtime
        / "tests/integration/adapters/transaction/test_real_transaction_egress_candidate_v4.py"
    ).resolve()
    manifest = (
        manifest_path
        or repository
        / "agent-runtime/tests/integration/adapters/transaction/evidence"
        / f"{RUN_ID}.manifest.json"
    ).resolve()
    executable = (python_executable or Path(sys.executable)).resolve()
    if journal_path.exists() or result_path.exists() or not executable.is_file():
        _invalid()

    _record(
        journal_path,
        manifest_sha256=manifest_sha256,
        sequence=1,
        event="preflight",
        status="started",
        reason=None,
        exclusive=True,
    )

    source_validated = False
    collection_validated = False
    failure_reason: str | None = None
    try:
        _validate_manifest_assets(
            repository=repository,
            manifest_path=manifest,
            manifest_sha256=manifest_sha256,
        )
        _record(
            journal_path,
            manifest_sha256=manifest_sha256,
            sequence=2,
            event="asset_binding",
            status="succeeded",
            reason=None,
        )
        completed = subprocess.run(
            [
                str(executable),
                "-I",
                "-c",
                _collection_probe_code(),
                str(source),
                str(runtime),
                str(live_test),
                str(runtime / "src"),
            ],
            cwd=repository,
            env=_safe_subprocess_environment(),
            capture_output=True,
            check=False,
            timeout=30,
        )
        if completed.returncode == 23:
            failure_reason = "python_import_source_invalid"
        elif completed.returncode == 24:
            source_validated = True
            failure_reason = "python_collection_failed"
        elif completed.returncode != 0:
            failure_reason = "python_import_failed"
        elif len(completed.stdout) + len(completed.stderr) > 1_048_576:
            source_validated = True
            failure_reason = "python_collection_failed"
        else:
            source_validated = True
            collection_validated = True
    except TransactionEgressHostPreflightError as error:
        failure_reason = (
            str(error)
            if str(error) in {"asset_hash_invalid", "manifest_binding_invalid"}
            else "manifest_binding_invalid"
        )
        _record(
            journal_path,
            manifest_sha256=manifest_sha256,
            sequence=2,
            event="asset_binding",
            status="failed",
            reason=failure_reason,
        )
    except (OSError, subprocess.SubprocessError):
        failure_reason = "python_import_failed"
    except BaseException:
        failure_reason = "preflight_internal_failure"

    status = "passed" if source_validated and collection_validated else "failed_unconsumed"
    _record(
        journal_path,
        manifest_sha256=manifest_sha256,
        sequence=3,
        event="python_collection",
        status=(
            "succeeded"
            if collection_validated
            else "skipped"
            if failure_reason in {"asset_hash_invalid", "manifest_binding_invalid"}
            else "failed"
        ),
        reason=failure_reason,
    )
    _record(
        journal_path,
        manifest_sha256=manifest_sha256,
        sequence=4,
        event="preflight",
        status=status,
        reason=failure_reason,
    )
    value: dict[str, object] = {
        "schemaVersion": HOST_SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": status,
        "sourceValidated": source_validated,
        "collectionValidated": collection_validated,
        "counts": {
            "databaseSelectorStatements": 0,
            "transactionSearchRequests": 0,
            "modelOutboundRequests": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "safety": {
            "transactionTypePersisted": False,
            "jwtPersisted": False,
            "databaseCredentialsPersisted": False,
            "rawOutputPersisted": False,
        },
        "failure": {"reason": failure_reason},
    }
    validated = validate_preflight_result(value, manifest_sha256=manifest_sha256)
    _write_exclusive(
        result_path,
        json.dumps(validated, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
    )
    validate_preflight_journal(journal_path, manifest_sha256=manifest_sha256)
    return validated


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size > 65_536:
        _invalid()
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(
                line,
                object_pairs_hook=_unique_object,
                parse_constant=lambda _value: _invalid(),
            )
            if not isinstance(value, dict):
                _invalid()
            records.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid()
    return records


def validate_preflight_journal(
    path: Path, *, manifest_sha256: str
) -> list[dict[str, Any]]:
    records = _load_jsonl(path)
    if len(records) != 4:
        _invalid()
    for index, record in enumerate(records, start=1):
        if (
            set(record) != _JOURNAL_KEYS
            or record["schemaVersion"] != HOST_SCHEMA_VERSION
            or record["runId"] != RUN_ID
            or record["manifestSha256"] != manifest_sha256
            or record["authorizationReference"] != AUTHORIZATION_REFERENCE
            or record["sequence"] != index
        ):
            _invalid()
    if records[0] != {
        "schemaVersion": HOST_SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "sequence": 1,
        "event": "preflight",
        "status": "started",
        "reason": None,
    }:
        _invalid()
    terminal = records[-1]
    if terminal["event"] != "preflight" or terminal["status"] not in {
        "passed",
        "failed_unconsumed",
    }:
        _invalid()
    asset_record = records[1]
    collection_record = records[2]
    passed = terminal["status"] == "passed"
    if (
        asset_record["event"] != "asset_binding"
        or asset_record["status"] not in {"succeeded", "failed"}
        or collection_record["event"] != "python_collection"
        or collection_record["status"] not in {"succeeded", "failed", "skipped"}
        or collection_record["reason"] != terminal["reason"]
        or (collection_record["status"] == "succeeded") is not passed
        or (collection_record["reason"] is None) is not passed
        or (asset_record["status"] == "failed")
        is not (collection_record["status"] == "skipped")
        or (
            asset_record["reason"]
            != (terminal["reason"] if asset_record["status"] == "failed" else None)
        )
    ):
        _invalid()
    return records


def validate_preflight_result(
    value: object, *, manifest_sha256: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RESULT_KEYS:
        _invalid()
    result = dict(value)
    if (
        result["schemaVersion"] != HOST_SCHEMA_VERSION
        or result["runId"] != RUN_ID
        or result["manifestSha256"] != manifest_sha256
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or result["status"] not in {"passed", "failed_unconsumed"}
        or type(result["sourceValidated"]) is not bool
        or type(result["collectionValidated"]) is not bool
    ):
        _invalid()
    counts = result["counts"]
    safety = result["safety"]
    failure = result["failure"]
    if (
        not isinstance(counts, Mapping)
        or set(counts)
        != {
            "databaseSelectorStatements",
            "transactionSearchRequests",
            "modelOutboundRequests",
            "retryCount",
            "resumeCount",
        }
        or any(type(item) is not int or item != 0 for item in counts.values())
        or not isinstance(safety, Mapping)
        or set(safety)
        != {
            "transactionTypePersisted",
            "jwtPersisted",
            "databaseCredentialsPersisted",
            "rawOutputPersisted",
        }
        or any(type(item) is not bool or item for item in safety.values())
        or not isinstance(failure, Mapping)
        or set(failure) != {"reason"}
        or failure["reason"] not in _FAILURE_REASONS
    ):
        _invalid()
    passed = result["status"] == "passed"
    if (
        result["collectionValidated"] is not passed
        or (passed and not result["sourceValidated"])
        or (result["collectionValidated"] and not result["sourceValidated"])
        or (failure["reason"] is None) is not passed
    ):
        _invalid()
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = execute_import_preflight(
        repository_root=arguments.repository_root,
        journal_path=arguments.journal,
        result_path=arguments.result,
        manifest_sha256=arguments.manifest_sha256,
        manifest_path=arguments.manifest,
    )
    return 0 if result["status"] == "passed" else 7


if __name__ == "__main__":
    raise SystemExit(main())
