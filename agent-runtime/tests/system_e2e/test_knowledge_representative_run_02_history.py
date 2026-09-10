"""Immutable run-02 outcome; remaining budget never authorizes another run."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).with_name("knowledge_representative_run_02")
REPO = Path(__file__).resolve().parents[3]
HEAD = "ab809be1f4fb71f1c01580fb782c039aaf1d64fb"
HASHES = {
    "authorization.json": "a60963c7f00456b3124a0322a55da9233f64cbab21190411d7c6c0a832d1b368",
    "consumed.json": "4ce5600957b146ed4b3bc2601350d9e11cc7384aa83266849af5f1d811042ac8",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "772064dceb6131fc198706d03f945f18ec68e7a4f3c62271eaf228f14926ccca",
    "event-006.json": "b64e093f455e29f983c94626334f62b0f14f9e1654388db2e2ee2e1e63b161de",
    "event-007.json": "5c60dc005de550eed5362803debb55c8a5ef5c54dcadccb9c1c675af331408d4",
    "event-008.json": "56cb3ab12dd03699c50e1813f31e8de2f3b1490ca8fd80486f2f8b0075dfffcb",
    "event-009.json": "70d02734ece257a73e0a41d463b636e374d6d94af5ce977d16dc16e9b543760f",
    "event-010.json": "a517f37b271c90a9db0bcce946160c1ed2b1d6b688a899ad6cbdd54a47a01795",
    "event-011.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-012.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "66ccac64d5b2bff47f0eb53ba2a47fadd3af07d90b3d1ffd1f73eeea3a25532a",
    "manifest.json": "c8b6a8e85167e2b320a1fa8781bc3af79b50509def7c624b3b7bbcee8de7cacc",
    "result.json": "d3ab38d039d36dd31e9c29a128111ee80f8ad87804d80b77d04a2ad8e4c5c77e",
    "started.json": "4ce5600957b146ed4b3bc2601350d9e11cc7384aa83266849af5f1d811042ac8",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


@pytest.mark.parametrize("name,sha", HASHES.items())
def test_exact_original_asset_bytes(name, sha):
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha


def test_frozen_protocol_is_from_authorized_commit_not_current_documents():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.54"
    assert auth["manifestSha256"] == HASHES["manifest.json"]
    assert manifest["runId"] == auth["runId"] == "knowledge-representative-uat-v2-20260910-02"
    assert manifest["knownBefore"] == dict(e2e=25, model=63)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=34, model=90)
    assert auth["limits"] == dict(e2e=9, model=27, search=36, embedding=18,
                                  rerank=36, business=0, retry=0, resume=0)
    for name in (
        "agent-runtime/tests/system_e2e/knowledge_representative_uat_v2.py",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v2.py",
        "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
        "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark.v1.json",
        "agent-runtime/src/agent_runtime/knowledge/rewrite_v9.py",
    ):
        raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == manifest["assets"][name]


def test_git_filters_preserve_original_newlines():
    for name in HASHES:
        path = (ROOT / name).relative_to(REPO).as_posix()
        raw = subprocess.check_output(["git", "hash-object", "--no-filters", path], cwd=REPO)
        filtered = subprocess.check_output(["git", "hash-object", path], cwd=REPO)
        assert raw == filtered


def test_legacy_manifest_binding_key_points_to_frozen_v2_not_v1_file():
    manifest = read("manifest.json")
    old_key = "serviceCenter/knowledge-runtime-binding.v1.json"
    actual_key = "serviceCenter/knowledge-runtime-binding.v2.json"
    raw = subprocess.check_output(["git", "show", f"{HEAD}:{actual_key}"], cwd=REPO)
    assert manifest["assets"][old_key] == manifest["assets"][actual_key] == hashlib.sha256(raw).hexdigest()
    # ServiceRoot's frozen path adapter was used by both preparation and services.
    frozen_runner = subprocess.check_output([
        "git", "show", f"{HEAD}:agent-runtime/tests/system_e2e/knowledge_representative_uat_v2.py"], cwd=REPO)
    assert b'path = "serviceCenter/knowledge-runtime-binding.v2.json"' in frozen_runner


def test_failure_stops_after_six_without_reusing_remaining_budget():
    result = read("result.json")
    assert result["status"] == "failed" and result["failureReason"] == "execution_or_case_failed"
    assert result["totals"] == dict(e2e=6, model=17, search=10, embedding=5,
                                    rerank=6, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and result["indexWrites"] == result["answer"] == 0
    assert [row["caseId"] for row in result["cases"]] == [
        "KRB-006", "KRB-004", "KRB-010", "KRB-011", "KRB-012", "KRB-017"]
    assert [row["passed"] for row in result["cases"]] == [True] * 5 + [False]
    assert result["notExecuted"] == ["KRB-019", "KRB-021", "KRB-023"]
    for kind in result["totals"]:
        assert sum(row["calls"][kind] for row in result["cases"]) == result["totals"][kind]
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [j["ordinal"] for j in journal] == list(range(1, 18))
    expected = []
    for row in result["cases"]:
        expected.extend((row["caseId"], task["taskId"]) for task in row["modelTasks"])
    assert [(j["caseId"], j["task"]) for j in journal] == expected
    assert read("manifest.json")["knownBefore"]["e2e"] + result["totals"]["e2e"] == 31
    assert read("manifest.json")["knownBefore"]["model"] + result["totals"]["model"] == 80
    assert result["cleanup"][-1] == dict(stage="cleanup", ownedProcessesStopped=True,
                                          rawLogsDeleted=True, secretScanPassed=True)
    assert all(e["clientsClosed"] for e in result["cleanup"] if e["stage"] == "runtime_cleanup")


def test_five_passed_have_actual_source_and_quote_binding_not_manual_usefulness():
    result = read("result.json")
    for row in result["cases"][:5]:
        assert row["httpStatus"] == 200 and row["status"] == "success"
        assert row["taskBindingValid"] and row["retrievalComplete"]
        assert row["sourceCheck"]["binding_valid"]
        assert all(passed for _, passed in row["sourceCheck"]["required_clauses"])
        assert row["validation"] == dict(phases=["coverage", "extractive"], failures=[])
        assert [(m["taskId"], m["taskVersion"]) for m in row["modelTasks"]] == [
            ("action_selection", "action-selection-v4"), ("knowledge_rewrite", "9"), ("knowledge_summary", "7")]
        assert all(m["status"] == "succeeded" and m["failureKind"] is None for m in row["modelTasks"])
        assert row["manualUsefulness"] == "not_assessed"
    for stage in ("path", "final_rank", "evidence"):
        assert result["cases"][0]["requiredSourcesByStage"][stage] == dict(small_2022_1=True, small_2023_2=True)


def test_invalid_output_is_before_retrieval_not_evidence_of_missing_corpus():
    failed = read("result.json")["cases"][-1]
    assert failed["httpStatus"] == 502 and failed["status"] == "downstream_failure"
    assert failed["modelTasks"] == [
        dict(taskId="action_selection", taskVersion="action-selection-v4", status="succeeded", failureKind=None),
        dict(taskId="knowledge_rewrite", taskVersion="9", status="failed", failureKind="invalid_output"),
    ]
    assert failed["calls"] == dict(e2e=1, model=2, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    assert failed["retrievalStages"] == [] and failed["planSha256"] is None
    assert failed["sourceCheck"] is None and not failed["retrievalComplete"]
    assert failed["validation"] == dict(phases=[], failures=[])
    assert failed["manualUsefulness"] == "not_assessed"


def test_finite_assets_exclude_queries_quotes_keys_and_bodies():
    forbidden = {"question", "quote", "content", "query_text", "focus", "systemInstruction", "raw_response", "jwt", "apiKey"}

    def check(value):
        if isinstance(value, dict):
            assert not set(value).intersection(forbidden)
            for nested in value.values():
                check(nested)
        elif isinstance(value, list):
            for nested in value:
                check(nested)

    for path in ROOT.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert re.search(r"sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw) is None
        for line in raw.splitlines():
            check(json.loads(line))
