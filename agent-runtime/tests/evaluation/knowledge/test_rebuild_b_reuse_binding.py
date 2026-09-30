"""Synthetic, read-only tests for the new B comparison-only reuse binding."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import cast

import pytest

from agent_runtime.knowledge.retrieval.contracts import KnowledgeSearchPort
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmEndpoint, ComparisonRunError, FrozenIdMapping, LocalRuntimeAdmission,
    _verify_provenance,
)
from tests.evaluation.knowledge.rebuild_b_local_runner import _expected_profile_config_sha256
from tests.evaluation.knowledge.rebuild_b_reuse_binding import (
    CONFIG_PATH, FIXTURE_PATH, OLD_COMMIT, OLD_DIRECTORY, OldBuild,
    ReuseBindingError, ScanOutcome, create_reuse_run, execute_reuse_scans,
    finalize_reuse_scans, freeze_new_reuse_input, git_blob, load_old_build,
    scan_receipt, spec_for_reuse, verify_reuse_provenance,
)


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


@pytest.fixture(scope="module")
def old() -> OldBuild:
    return load_old_build()


def _intent(old: OldBuild, run_id: str = "knowledge-b-reuse-fake-01") -> bytes:
    head = _head()
    prior = json.loads(old.spec.intent_raw)["profileParameters"]
    parameters = {domain: {**value,
        "configSha256": _expected_profile_config_sha256(head, domain)}
        for domain, value in prior.items()}
    return freeze_new_reuse_input(
        old=old, run_id=run_id, frozen_head=head,
        profile_parameters=parameters,
        config_raw=git_blob(head, CONFIG_PATH),
        fixture_raw=git_blob(head, FIXTURE_PATH),
    )


def _scan_artifacts(old: OldBuild, intent_raw: bytes,
                    *, execution_kind: str = "local") -> tuple[dict[str, bytes],
                                                                  FrozenIdMapping,
                                                                  FrozenIdMapping]:
    source_raw = dict(old.blobs)["source-id-mapping.json"]
    candidate_raw = dict(old.blobs)["candidate-id-mapping.json"]
    source_receipt = scan_receipt(
        arm="source", intent_raw=intent_raw, map_raw=source_raw, es_http=64,
        mapping_version="agent-knowledge-tax-v3-policy-context-v1",
        execution_kind=execution_kind)
    candidate_receipt = scan_receipt(
        arm="candidate", intent_raw=intent_raw, map_raw=candidate_raw, es_http=64,
        mapping_version="agent-knowledge-tax-v3-policy-context-v1",
        execution_kind=execution_kind)
    final_raw = finalize_reuse_scans(
        intent_raw=intent_raw, source_scan_raw=source_receipt,
        candidate_scan_raw=candidate_receipt,
        source_map_raw=source_raw, candidate_map_raw=candidate_raw)
    intent = json.loads(intent_raw)
    attempt_raw = (json.dumps({
        "schemaVersion": 2, "runId": intent["runId"],
        "frozenHead": intent["frozenHead"],
        "reuseIntentSha256": sha256(intent_raw).hexdigest(),
        "executionKind": execution_kind, "status": "consumed",
        "sourceEsHttpMax": 64, "candidateEsHttpMax": 64,
        "builderEsHttpMax": 0, "builderEmbeddingHttpMax": 0,
        "builderWriteOpsMax": 0, "paid": 0, "retry": 0, "resume": 0,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    terminal_raw = (json.dumps({
        "schemaVersion": 2, "runId": intent["runId"],
        "reuseIntentSha256": sha256(intent_raw).hexdigest(),
        "status": "scanned_read_only", "reason": "none",
        "executionKind": execution_kind,
        "completedArms": ["source", "candidate"],
        "sourceEsHttp": 64, "candidateEsHttp": 64,
        "builderEsHttp": 0, "builderEmbeddingHttp": 0,
        "builderWriteOps": 0, "paid": 0, "retry": 0, "resume": 0,
        "reuseFinalSha256": sha256(final_raw).hexdigest(),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    sidecars = {"reuseIntent": intent_raw, "reuseFinal": final_raw,
                "reuseAttempt": attempt_raw, "reuseTerminal": terminal_raw,
                "sourceScanResult": source_receipt,
                "candidateScanResult": candidate_receipt}
    return sidecars, old.source_map, old.candidate_map


def _admission(old: OldBuild, intent_raw: bytes) -> LocalRuntimeAdmission:
    intent = json.loads(intent_raw)
    run_id = intent["runId"]
    return LocalRuntimeAdmission(run_id, intent["frozenHead"], (
        ("baseline", old.spec.source_corpus.index_name,
         old.spec.source_corpus.index_uuid, f"b-{run_id}-{'a' * 16}-read", "b" * 64, 101),
        ("candidate", old.spec.candidate_corpus.index_name,
         old.spec.candidate_corpus.index_uuid, f"b-{run_id}-{'c' * 16}-read", "d" * 64, 102),
    ), "e" * 64)


def _verify(old: OldBuild, sidecars: dict[str, bytes]) -> tuple[str, str]:
    spec = spec_for_reuse(old, intent_raw=sidecars["reuseIntent"],
                          final_raw=sidecars["reuseFinal"])
    baseline = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                           dict(spec.profile_snapshots)["baseline"], old.source_map)
    candidate = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                            dict(spec.profile_snapshots)["candidate"],
                            old.candidate_map)
    return verify_reuse_provenance(spec, baseline, candidate, sidecars,
                                   _admission(old, sidecars["reuseIntent"]))


def test_old_committed_build_chain_and_new_freeze_are_separate(old: OldBuild) -> None:
    assert old.old_head != _head()
    assert len(old.file_sha256) == 10
    assert len(old.source_map.records) == len(old.candidate_map.records) == 15521
    intent = json.loads(_intent(old))
    assert intent["oldGitCommit"] == OLD_COMMIT
    assert intent["oldGitDirectory"] == OLD_DIRECTORY
    assert intent["oldBuilderRunId"] != intent["runId"]
    assert intent["builderBudget"] == {"candidates": 0, "esHttp": 0,
        "embeddingHttp": 0, "writeOps": 0, "onlineAliasWrites": 0,
        "paid": 0, "retry": 0, "resume": 0}
    assert intent["mappingScanBudget"] == {
        "sourceEsHttp": 64, "candidateEsHttp": 64, "retry": 0, "resume": 0}
    assert intent["comparisonBudget"]["typedSearch"] == 44
    assert intent["comparisonBudget"]["metadataEsHttp"] == 30


def test_reuse_provenance_accepts_exact_synthetic_local_receipts(old: OldBuild) -> None:
    sidecars, _, _ = _scan_artifacts(old, _intent(old))
    proof_sha, kind = _verify(old, sidecars)
    assert len(proof_sha) == 64 and kind == "local"


@pytest.mark.parametrize("drift", [
    "missing_attempt", "missing_terminal", "attempt_run", "attempt_head",
    "terminal_count", "terminal_status", "terminal_final", "terminal_arms",
])
def test_reuse_provenance_requires_new_run_scan_execution(
        old: OldBuild, drift: str) -> None:
    sidecars, _, _ = _scan_artifacts(old, _intent(old))
    if drift.startswith("missing_"):
        del sidecars["reuseAttempt" if drift == "missing_attempt" else "reuseTerminal"]
    else:
        key = "reuseAttempt" if drift.startswith("attempt_") else "reuseTerminal"
        document = json.loads(sidecars[key])
        if drift == "attempt_run":
            document["runId"] = "knowledge-b-reuse-other-01"
        elif drift == "attempt_head":
            document["frozenHead"] = "0" * 40
        elif drift == "terminal_count":
            document["candidateEsHttp"] = 63
        elif drift == "terminal_status":
            document["status"] = "failed"
        elif drift == "terminal_final":
            document["reuseFinalSha256"] = "0" * 64
        else:
            document["completedArms"] = ["source"]
        sidecars[key] = (json.dumps(document, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ComparisonRunError):
        _verify(old, sidecars)


def test_comparator_dispatch_accepts_only_exact_v2_sidecars(old: OldBuild) -> None:
    sidecars, _, _ = _scan_artifacts(old, _intent(old))
    spec = spec_for_reuse(old, intent_raw=sidecars["reuseIntent"],
                          final_raw=sidecars["reuseFinal"])
    baseline = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                           dict(spec.profile_snapshots)["baseline"], old.source_map)
    candidate = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                            dict(spec.profile_snapshots)["candidate"], old.candidate_map)
    admission = _admission(old, sidecars["reuseIntent"])
    proof_sha, kind = _verify_provenance(spec, baseline, candidate, sidecars, admission)
    assert len(proof_sha) == 64 and kind == "local"
    with pytest.raises(ComparisonRunError):
        _verify_provenance(spec, baseline, candidate,
                           {**sidecars, "builderResult": b"{}\n"}, admission)


@pytest.mark.parametrize("drift", ["old_blob", "new_config", "new_id", "fake_scan",
                                    "old_run", "scan_budget", "case_gold"])
def test_reuse_provenance_rejects_drift(old: OldBuild, drift: str) -> None:
    sidecars, _, _ = _scan_artifacts(old, _intent(old),
        execution_kind="fake" if drift == "fake_scan" else "local")
    reader = git_blob
    if drift in ("old_run", "scan_budget", "case_gold"):
        intent = json.loads(sidecars["reuseIntent"])
        if drift == "old_run":
            intent["oldBuilderRunId"] = "different-run"
        elif drift == "scan_budget":
            intent["mappingScanBudget"]["sourceEsHttp"] = 65
        else:
            intent["casePlanGoldSha256"] = "0" * 64
        sidecars["reuseIntent"] = (json.dumps(intent, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")) + "\n").encode()
    elif drift == "new_id":
        raw = json.loads(dict(old.blobs)["source-id-mapping.json"])
        raw["records"][0]["contentSha256"] = "0" * 64
        changed = (json.dumps(raw, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")) + "\n").encode()
        wrong = FrozenIdMapping.from_bytes(changed,
            expected_sha256=sha256(changed).hexdigest())
        spec = spec_for_reuse(old, intent_raw=sidecars["reuseIntent"],
                              final_raw=sidecars["reuseFinal"])
        baseline = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                               dict(spec.profile_snapshots)["baseline"], wrong)
        candidate = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                                dict(spec.profile_snapshots)["candidate"],
                                old.candidate_map)
        with pytest.raises(ComparisonRunError):
            verify_reuse_provenance(spec, baseline, candidate, sidecars,
                                     _admission(old, sidecars["reuseIntent"]))
        return
    elif drift in ("old_blob", "new_config"):
        def changed_reader(commit: str, path: str) -> bytes:
            raw = git_blob(commit, path)
            if drift == "old_blob" and commit == OLD_COMMIT and path.endswith("/result.json"):
                return raw + b" "
            if drift == "new_config" and commit == _head() and path == CONFIG_PATH:
                return raw + b" "
            return raw
        reader = changed_reader
    spec = spec_for_reuse(old, intent_raw=sidecars["reuseIntent"],
                          final_raw=sidecars["reuseFinal"])
    baseline = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                           dict(spec.profile_snapshots)["baseline"], old.source_map)
    candidate = ArmEndpoint(cast(KnowledgeSearchPort, object()),
                            dict(spec.profile_snapshots)["candidate"],
                            old.candidate_map)
    with pytest.raises(ComparisonRunError):
        verify_reuse_provenance(spec, baseline, candidate, sidecars,
                                _admission(old, sidecars["reuseIntent"]),
                                read_blob=reader)


def test_fresh_scan_one_shot_fake_and_failed_count_terminal(old: OldBuild,
                                                              tmp_path: Path) -> None:
    run_id = "knowledge-b-reuse-fake-02"
    intent_raw = _intent(old, run_id)
    run = tmp_path / run_id
    create_reuse_run(run, intent_raw, frozen_context=lambda _: True)
    with pytest.raises(ReuseBindingError, match="reuse_run_already_used"):
        create_reuse_run(run, intent_raw, frozen_context=lambda _: True)
    maps = dict(old.blobs)
    calls = {"source": 0, "candidate": 0}

    def scan(arm: str, _corpus: object, _limit: int) -> ScanOutcome:
        calls[arm] = 7
        raise RuntimeError("would contain untrusted response")

    with pytest.raises(ReuseBindingError, match="scan_failed"):
        execute_reuse_scans(run, scan_arm=scan,
                            observed_calls=lambda arm: calls[arm],
                            execution_kind="fake", frozen_context=lambda _: True)
    terminal = json.loads((run / "reuse-scan-terminal.json").read_bytes())
    assert terminal["status"] == "failed"
    assert terminal["sourceEsHttp"] == 7 and terminal["candidateEsHttp"] == 0
    assert terminal["builderEsHttp"] == terminal["builderWriteOps"] == 0
    assert "would contain" not in (run / "reuse-scan-terminal.json").read_text()
    with pytest.raises(ReuseBindingError, match="reuse_run_already_used"):
        execute_reuse_scans(run, scan_arm=scan,
                            observed_calls=lambda arm: calls[arm],
                            execution_kind="fake", frozen_context=lambda _: True)


def test_fresh_scan_fake_complete_still_cannot_admit_local(old: OldBuild,
                                                            tmp_path: Path) -> None:
    run_id = "knowledge-b-reuse-fake-03"
    intent_raw = _intent(old, run_id)
    run = tmp_path / run_id
    create_reuse_run(run, intent_raw, frozen_context=lambda _: True)
    maps = dict(old.blobs)
    calls = {"source": 0, "candidate": 0}

    def scan(arm: str, _corpus: object, limit: int) -> ScanOutcome:
        assert limit == 64
        calls[arm] = 64
        return ScanOutcome(maps[f"{arm}-id-mapping.json"], 64,
                           "agent-knowledge-tax-v3-policy-context-v1")

    final_raw = execute_reuse_scans(run, scan_arm=scan,
        observed_calls=lambda arm: calls[arm], execution_kind="fake",
        frozen_context=lambda _: True)
    assert json.loads(final_raw)["runId"] == run_id
    assert json.loads((run / "reuse-scan-terminal.json").read_bytes())["status"] == "scanned_read_only"
    sidecars = {"reuseIntent": intent_raw, "reuseFinal": final_raw,
        "reuseAttempt": (run / "reuse-scan-attempt.json").read_bytes(),
        "reuseTerminal": (run / "reuse-scan-terminal.json").read_bytes(),
        "sourceScanResult": (run / "source-scan-result.json").read_bytes(),
        "candidateScanResult": (run / "candidate-scan-result.json").read_bytes()}
    with pytest.raises(ComparisonRunError):
        _verify(old, sidecars)
