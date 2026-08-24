from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from tests.integration.adapters.frozen_manifest import (
    write_manifest_bound_to_current_tree,
)
from tests.integration.adapters.transaction.egress_candidate_v3 import sha256_file
from tests.integration.adapters.transaction.egress_candidate_v3_host import (
    RUN_ID,
    TransactionEgressHostPreflightError,
    _safe_subprocess_environment,
    execute_import_preflight,
    load_strict_json,
    validate_preflight_journal,
    validate_preflight_result,
)


ROOT = Path(__file__).resolve().parents[5]
MANIFEST = (
    ROOT
    / "agent-runtime/tests/integration/adapters/transaction/evidence"
    / f"{RUN_ID}.manifest.json"
)


def _current_manifest(tmp_path: Path) -> Path:
    return write_manifest_bound_to_current_tree(
        load_strict_json(MANIFEST),
        repository_root=ROOT,
        destination=tmp_path / "current-non-live-manifest.json",
        collection_names=("history", "assetHashes"),
    )


def test_real_isolated_import_resolves_current_runtime_source(tmp_path: Path) -> None:
    journal = tmp_path / "preflight.jsonl"
    result = tmp_path / "result.json"
    manifest = _current_manifest(tmp_path)
    manifest_sha256 = sha256_file(manifest)

    value = execute_import_preflight(
        repository_root=ROOT,
        journal_path=journal,
        result_path=result,
        manifest_sha256=manifest_sha256,
        manifest_path=manifest,
        python_executable=Path(sys.executable),
    )

    assert value["status"] == "passed"
    assert value["sourceValidated"] is True
    assert value["collectionValidated"] is True
    assert value["counts"] == {
        "databaseSelectorStatements": 0,
        "transactionSearchRequests": 0,
        "modelOutboundRequests": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert len(validate_preflight_journal(journal, manifest_sha256=manifest_sha256)) == 4
    assert validate_preflight_result(
        load_strict_json(result), manifest_sha256=manifest_sha256
    ) == value


def test_wrong_source_fails_unconsumed_without_external_calls(tmp_path: Path) -> None:
    journal = tmp_path / "preflight.jsonl"
    result = tmp_path / "result.json"
    manifest = _current_manifest(tmp_path)
    manifest_sha256 = sha256_file(manifest)

    value = execute_import_preflight(
        repository_root=ROOT,
        journal_path=journal,
        result_path=result,
        manifest_sha256=manifest_sha256,
        manifest_path=manifest,
        python_executable=Path(sys.executable),
        source_root=tmp_path / "missing-source",
    )

    assert value["status"] == "failed_unconsumed"
    assert value["sourceValidated"] is False
    assert value["collectionValidated"] is False
    assert value["failure"]["reason"] == "python_import_source_invalid"
    assert all(item == 0 for item in value["counts"].values())
    assert not any(value["safety"].values())


def test_child_environment_excludes_secrets_and_python_path(tmp_path: Path) -> None:
    journal = tmp_path / "preflight.jsonl"
    result = tmp_path / "result.json"
    manifest = _current_manifest(tmp_path)
    manifest_sha256 = sha256_file(manifest)
    captured: dict[str, str] = {}

    def run_probe(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del args
        captured.update(cast(dict[str, str], kwargs["env"]))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    with patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "forbidden-key",
            "TRANSACTION_EGRESS_LIVE_USER_JWT": "forbidden-jwt",
            "PYTHONPATH": "forbidden-path",
        },
        clear=False,
    ), patch(
        "tests.integration.adapters.transaction.egress_candidate_v3_host.subprocess.run",
        side_effect=run_probe,
    ):
        value = execute_import_preflight(
            repository_root=ROOT,
            journal_path=journal,
            result_path=result,
            manifest_sha256=manifest_sha256,
            manifest_path=manifest,
            python_executable=Path(sys.executable),
        )

    assert value["status"] == "passed"
    assert "LLM_API_KEY" not in captured
    assert "TRANSACTION_EGRESS_LIVE_USER_JWT" not in captured
    assert "PYTHONPATH" not in captured
    assert captured == _safe_subprocess_environment()


def test_collection_failure_or_existing_evidence_fails_closed(tmp_path: Path) -> None:
    journal = tmp_path / "preflight.jsonl"
    result = tmp_path / "result.json"
    manifest = _current_manifest(tmp_path)
    manifest_sha256 = sha256_file(manifest)

    with patch(
        "tests.integration.adapters.transaction.egress_candidate_v3_host.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=24, stdout=b"collection failed", stderr=b""
        ),
    ):
        value = execute_import_preflight(
            repository_root=ROOT,
            journal_path=journal,
            result_path=result,
            manifest_sha256=manifest_sha256,
            manifest_path=manifest,
            python_executable=Path(sys.executable),
        )
    assert value["status"] == "failed_unconsumed"
    assert value["sourceValidated"] is True
    assert value["collectionValidated"] is False
    assert value["failure"]["reason"] == "python_collection_failed"

    with pytest.raises(
        TransactionEgressHostPreflightError,
        match="transaction.egress_host_preflight_invalid",
    ):
        execute_import_preflight(
            repository_root=ROOT,
            journal_path=journal,
            result_path=result,
            manifest_sha256=manifest_sha256,
            manifest_path=manifest,
            python_executable=Path(sys.executable),
        )


def test_strict_result_rejects_nonzero_external_count() -> None:
    manifest_sha256 = sha256_file(MANIFEST)
    value = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": "P3_00:GATE-026",
        "status": "passed",
        "sourceValidated": True,
        "collectionValidated": True,
        "counts": {
            "databaseSelectorStatements": 1,
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
        "failure": {"reason": None},
    }

    with pytest.raises(TransactionEgressHostPreflightError):
        validate_preflight_result(value, manifest_sha256=manifest_sha256)


def test_asset_hash_failure_is_durable_and_skips_collection(tmp_path: Path) -> None:
    current_manifest = _current_manifest(tmp_path)
    manifest_value = json.loads(current_manifest.read_text(encoding="utf-8"))
    manifest_value["assetHashes"][0]["sha256"] = "0" * 64
    invalid_manifest = tmp_path / "manifest.json"
    invalid_manifest.write_text(
        json.dumps(manifest_value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = sha256_file(invalid_manifest)
    journal = tmp_path / "preflight.jsonl"
    result = tmp_path / "result.json"

    with patch(
        "tests.integration.adapters.transaction.egress_candidate_v3_host.subprocess.run"
    ) as subprocess_run:
        value = execute_import_preflight(
            repository_root=ROOT,
            journal_path=journal,
            result_path=result,
            manifest_sha256=manifest_sha256,
            manifest_path=invalid_manifest,
            python_executable=Path(sys.executable),
        )

    subprocess_run.assert_not_called()
    assert value["status"] == "failed_unconsumed"
    assert value["failure"]["reason"] == "asset_hash_invalid"
    records = validate_preflight_journal(journal, manifest_sha256=manifest_sha256)
    assert [record["status"] for record in records] == [
        "started",
        "failed",
        "skipped",
        "failed_unconsumed",
    ]


def test_strict_journal_rejects_inconsistent_middle_terminal_pair(tmp_path: Path) -> None:
    journal = tmp_path / "preflight.jsonl"
    journal.write_text(
        "\n".join(
            (
                '{"schemaVersion":1,"runId":"transaction-egress-v3-20260817-candidate-03",'
                '"manifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"authorizationReference":"P3_00:GATE-026","sequence":1,"event":"preflight",'
                '"status":"started","reason":null}',
                '{"schemaVersion":1,"runId":"transaction-egress-v3-20260817-candidate-03",'
                '"manifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"authorizationReference":"P3_00:GATE-026","sequence":2,"event":"asset_binding",'
                '"status":"succeeded","reason":null}',
                '{"schemaVersion":1,"runId":"transaction-egress-v3-20260817-candidate-03",'
                '"manifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"authorizationReference":"P3_00:GATE-026","sequence":3,"event":"python_collection",'
                '"status":"failed","reason":"python_collection_failed"}',
                '{"schemaVersion":1,"runId":"transaction-egress-v3-20260817-candidate-03",'
                '"manifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"authorizationReference":"P3_00:GATE-026","sequence":4,"event":"preflight",'
                '"status":"passed","reason":null}',
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(TransactionEgressHostPreflightError):
        validate_preflight_journal(journal, manifest_sha256="a" * 64)
