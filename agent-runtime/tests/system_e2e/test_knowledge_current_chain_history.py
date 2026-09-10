"""Preserve the consumed failure without reconstructing discarded model text."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).with_name("knowledge_current_chain_01")
HEAD = "44cfb95b018dae508662e61184894422f1f2fe83"
HASHES = {
    "manifest.json": "e81276d7708f06d871e64af82f13269edaf91c323f29c7a75c37999a722d6bba",
    "started.json": "8cac74b06ae71b22018a757742c15d2b087ec801add129b05810930170eecf5d",
    "consumed.json": "35473440ac3f8914412f4ed0bec6a02257c61f45e664787dc2621b690e4a04f2",
    "journal-001.json": "8dd02614dae4b461709b22621dbcee9e454ce761802ced60a256cfd13d369360",
    "journal-002.json": "80220a73a015d14ce0ece7c1fc3d12d9b0ac277e97549e55cdfe57c2febfb154",
    "result.json": "f525f6e27a78dd63fc0f9acf0855bca5d9ff39528842744f359d1c6af1420ae1",
}


def test_immutable_failure_and_precise_proof_boundary():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    assert manifest["frozenHead"] == HEAD
    assert manifest["knownPaidBefore"] == 55
    assert manifest["knownEndToEndBefore"] == 22
    result = json.loads((ROOT / "result.json").read_bytes())
    assert result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed"
    assert result["modelAttempts"] == 2 and result["runtimeCalls"] == 1
    assert result["warmupCalls"] == 1
    assert result["counts"] == dict(search=0, embedding=0, rerank=0)
    assert all(result[key] == 0 for key in ("business", "answer", "retry", "resume", "indexWrites"))
    assert all(result[key] is True for key in (
        "ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed", "profileVerifierStartupPassed",
    ))
    row = result["case"]
    assert row["caseId"] == "KRB-015" and row["passed"] is False
    assert row["status"] == "downstream_failure"
    assert row["failureCode"] == "knowledge.rewrite_failure"
    assert row["clientsClosed"] is True
    assert row["plan"] is None and row["sourceCheck"] is None
    assert row["evidenceHashes"] == [] and row["http"] == []
    assert row["validation"] == dict(phases=[], failures=[])
    # Decoder success is not semantic acceptance, retrieval success or UAT Pass.
    assert [(r["taskId"], r["taskVersion"], r["status"], r["failureKind"])
            for r in row["modelTaskStates"]] == [
        ("action_selection", "action-selection-v4", "succeeded", None),
        ("knowledge_rewrite", "8", "succeeded", None),
    ]
    for ordinal, task in ((1, "action_selection"), (2, "knowledge_rewrite")):
        event = json.loads((ROOT / f"journal-{ordinal:03d}.json").read_bytes())
        assert event["ordinal"] == ordinal and event["taskId"] == task
        assert event["manifestSha256"] == HASHES["manifest.json"]
        assert len(event["requestSha256"]) == 64


def test_frozen_runner_and_guard_sources_remain_traceable():
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    for path in (
        "agent-runtime/tests/system_e2e/knowledge_current_chain_v1.py",
        "agent-runtime/tests/system_e2e/test_knowledge_current_chain_v1.py",
        "agent-runtime/src/agent_runtime/knowledge/semantic_planner.py",
        "agent-runtime/src/agent_runtime/knowledge/document_reference_semantics.py",
    ):
        original = subprocess.check_output(["git", "show", f"{HEAD}:{path}"], cwd=ROOT)
        assert hashlib.sha256(original).hexdigest() == manifest["assets"][path]
