"""Finite immutable results, not authorization for another request."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).with_name("knowledge_representative_run_01")
REPO = Path(__file__).resolve().parents[3]
HEAD = "cf848006fc48cd09d4f732177967ae2c2e9864a4"
HASHES = {
    "authorization.json": "d9e04889960bb7c155eba8dce31e6b49f145c2d2cd34791330cbc5730a3e51b6",
    "consumed.json": "73c91121ca6b1c378833479409d3cf5b88f6ce8ca12a42bf8e7b58ea4c4e8103",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "cebbba0db6d4785f4d8b09a18f36c3dc0d779fd9a415c279b79d923dfddee454",
    "event-006.json": "7da88a1bb42e05a1186cb79943f6490d955d1ee674da54b2daf4897d2c924393",
    "event-007.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-008.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "523a8f710dcc56fe12b490a3802935d1c9ccb81c8874de0713d6e683083581dd",
    "manifest.json": "5dee5f15977deb3637dc5a901df04ccc275dbb8b6073020f4a0a8b9f145112e9",
    "result.json": "18d666dcd0c29a50f5d8bb08ebcb92079ee9806dbe26a85d578b27be747187c0",
    "started.json": "73c91121ca6b1c378833479409d3cf5b88f6ce8ca12a42bf8e7b58ea4c4e8103",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


@pytest.mark.parametrize("name,sha", HASHES.items())
def test_exact_original_asset_bytes(name, sha):
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha


def test_frozen_contract_is_read_from_commit_not_current_plan():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.51"
    assert manifest["knownBefore"] == dict(e2e=23, model=57)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=33, model=87)
    for name in (
        "agent-runtime/tests/system_e2e/knowledge_representative_uat_v1.py",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v1.py",
        "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
    ):
        raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == manifest["assets"][name]


def test_git_filters_preserve_original_newlines_and_every_asset():
    for name in HASHES:
        path = (ROOT / name).relative_to(REPO).as_posix()
        raw = subprocess.check_output(["git", "hash-object", "--no-filters", path], cwd=REPO)
        filtered = subprocess.check_output(["git", "hash-object", path], cwd=REPO)
        assert raw == filtered


def test_failure_stops_after_two_and_preserves_exact_task_and_call_ledger():
    result = read("result.json")
    assert result["status"] == "failed"
    assert result["totals"] == dict(e2e=2, model=6, search=6, embedding=3, rerank=4, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and result["indexWrites"] == result["answer"] == 0
    assert [r["caseId"] for r in result["cases"]] == ["KRB-015", "KRB-006"]
    assert [r["passed"] for r in result["cases"]] == [True, False]
    assert len(result["notExecuted"]) == 8
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [j["ordinal"] for j in journal] == list(range(1, 7))
    assert [j["task"] for j in journal] == ["action_selection", "knowledge_rewrite", "knowledge_summary"] * 2
    for row in result["cases"]:
        assert [(m["taskId"], m["taskVersion"]) for m in row["modelTasks"]] == [
            ("action_selection", "action-selection-v4"), ("knowledge_rewrite", "9"), ("knowledge_summary", "7")]
        assert all(m["status"] == "succeeded" and m["failureKind"] is None for m in row["modelTasks"])
        assert row["validation"] == dict(phases=["coverage", "extractive"], failures=[])
    assert result["cleanup"][-1] == dict(stage="cleanup", ownedProcessesStopped=True,
                                          rawLogsDeleted=True, secretScanPassed=True)
    assert all(e["clientsClosed"] for e in result["cleanup"] if e["stage"] == "runtime_cleanup")


def test_missing_source_is_before_fusion_not_a_corpus_missing_or_decoder_claim():
    ok, failed = read("result.json")["cases"]
    assert ok["sourceCheck"]["binding_valid"]
    assert all(passed for _, passed in ok["sourceCheck"]["required_clauses"])
    assert failed["status"] == "no_result" and failed["retrievalComplete"]
    for stage in ("path", "final_rank", "evidence"):
        assert failed["requiredSourcesByStage"][stage] == dict(small_2022_1=True, small_2023_2=False)
    paths = [r for r in failed["retrievalStages"] if r["stage"] == "path"]
    assert {p["path"] for p in paths} == {"keyword", "vector"}
    assert all(p["status"] == "candidates" and len(p["candidates"]) == 20 for p in paths)
    # Same snapshot's earlier fixed-query result proves availability, not live success.
    benchmark = REPO / "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark.document_number.result.v1.jsonl"
    manifest = read("manifest.json")
    assert hashlib.sha256(benchmark.read_bytes()).hexdigest() == manifest["assets"][benchmark.relative_to(REPO).as_posix()]
    rows = [json.loads(line) for line in benchmark.read_bytes().splitlines()]
    assert rows[0]["datasetSha256"] == manifest["datasetSha256"]
    item = next(r for r in rows if r.get("event") == "case" and r.get("caseId") == "KRB-006")
    assert item["metrics"]["necessary_recall_at_k"] == item["metrics"]["evidence_coverage"] == 1
    assert failed["manualUsefulness"] == "not_assessed"


def test_finite_assets_do_not_store_queries_quotes_keys_or_bodies():
    forbidden = {"question", "quote", "content", "query_text", "focus", "systemInstruction", "raw_response", "jwt", "apiKey"}
    def check(value):
        if isinstance(value, dict):
            assert not set(value).intersection(forbidden)
            for nested in value.values(): check(nested)
        elif isinstance(value, list):
            for nested in value: check(nested)
    for path in ROOT.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert re.search(r"sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw) is None
        for line in raw.splitlines(): check(json.loads(line))
