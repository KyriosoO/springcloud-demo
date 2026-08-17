from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate_v3 import (
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_lifecycle,
    validate_manifest,
    validate_result,
)
from tests.integration.adapters.transaction.egress_candidate_v3_host import (
    validate_preflight_journal,
    validate_preflight_result,
)


ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent / "evidence"
EXPECTED_SHA256 = {
    f"{RUN_ID}.manifest.json": "9c1fb119f98fa9f1dc9bbd6904955d222c26fb39c837c179d3a85c1d883e6460",
    f"{RUN_ID}.authorization.json": "ca8983463fc051cf87bc563658bbe80cd583453de4547cd4c81df6524522970c",
    f"{RUN_ID}.host-preflight.jsonl": "869e441bca5b85dcf71508d5f5a7e94fa8fb7f2a981eb0850f8a082a030eb2f4",
    f"{RUN_ID}.host-result.json": "ca87a7db00f38890d9f1cb17e3acd1dc520ddbd814e1496ca2b9b9b9bf1a6f2c",
    f"{RUN_ID}.lifecycle.jsonl": "b5bb3e3d9413ad3a98ca9f34b0c76a6fd4b36c7c36d94ddf7aa5902827b7019f",
    f"{RUN_ID}.result.json": "eb5003cdc31a25a5aa2c201250fa00e4d7e5291aaf6482ffce63c3b5c8070b7d",
}


def test_candidate03_failed_unconsumed_history_is_exact_and_non_reusable() -> None:
    paths = {name: EVIDENCE / name for name in EXPECTED_SHA256}
    assert {name: sha256_file(path) for name, path in paths.items()} == EXPECTED_SHA256

    manifest_sha256 = EXPECTED_SHA256[f"{RUN_ID}.manifest.json"]
    validate_manifest(
        load_strict_json(paths[f"{RUN_ID}.manifest.json"]),
        repository_root=ROOT,
    )
    validate_authorization(
        load_strict_json(paths[f"{RUN_ID}.authorization.json"]),
        manifest_sha256=manifest_sha256,
    )
    validate_preflight_journal(
        paths[f"{RUN_ID}.host-preflight.jsonl"],
        manifest_sha256=manifest_sha256,
    )
    host_result = validate_preflight_result(
        load_strict_json(paths[f"{RUN_ID}.host-result.json"]),
        manifest_sha256=manifest_sha256,
    )
    lifecycle = validate_lifecycle(
        paths[f"{RUN_ID}.lifecycle.jsonl"],
        manifest_sha256=manifest_sha256,
        consumed_path=EVIDENCE / f"{RUN_ID}.authorization.consumed.json",
    )
    result = validate_result(load_strict_json(paths[f"{RUN_ID}.result.json"]))

    assert host_result["status"] == "passed"
    assert lifecycle.status == "failed_unconsumed"
    assert lifecycle.failure_phase == "model_call"
    assert lifecycle.failure_reason == "model_call_failed"
    assert lifecycle.transaction_search_started == 1
    assert lifecycle.transaction_search_terminal == 1
    assert lifecycle.answer_started == lifecycle.answer_terminal == 0
    assert lifecycle.consumed is False
    assert result["status"] == "failed_unconsumed"
    assert result["counts"] == {
        "transactionSearchStarted": 1,
        "transactionSearchTerminal": 1,
        "answerStarted": 0,
        "answerTerminal": 0,
        "validAnswers": 0,
        "otherTransactionEndpoints": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert result["safety"]["forbiddenPayloadFieldCount"] == 0
    assert result["safety"]["forbiddenLiteralCount"] == 7
    assert not (EVIDENCE / f"{RUN_ID}.authorization.consumed.json").exists()
