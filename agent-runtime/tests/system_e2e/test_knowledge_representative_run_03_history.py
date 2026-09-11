"""Run-03 originals and finite success evidence; prior failed runs stay failed."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).with_name("knowledge_representative_run_03")
REPO = Path(__file__).resolve().parents[3]
HEAD = "5fe5c0fecb7f0491c186cc4b0d4e5e625c2defe6"
RUN_ID = "knowledge-representative-uat-v3-20260911-03"
CASE_IDS = ["KRB-017", "KRB-019", "KRB-021", "KRB-023"]
HASHES = {
    "authorization.json": "7f1860e493c6ea745d503b0f6fa2cc15144d8430e0eec1041164cb7cc745124b",
    "consumed.json": "e8342394f090c3103e77f02090b26953a645b4db9380e2706968fff1d929acc3",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "9dd38fdffb8363e8d87bee38d314528af9c7d5a1225621f9555bd7dc58f4a2d3",
    "event-006.json": "999630c92e6ac4266fe302e7e6059f437e5b6e90104404cb959fc6275d00f18a",
    "event-007.json": "8df52937b6d4268958544ff20c3dc8caee2c650f0ce635f964deee1514054510",
    "event-008.json": "7f32b7d156e8aff553c65444afdfc4c03cdea45c711bba43d60dd1f1cc393741",
    "event-009.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-010.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "28ec664786e1d567931d35f3e09b646281534781896ff3839cfec3319f2d05c5",
    "manifest.json": "2ea733b87928e6125cbf97ba8c19766650a9a780595e626472bcaea346a524db",
    "result.json": "6652ecba3be238c06559a9f0b7333c0cc8469663669ad31912c0a7aca3b8a2c5",
    "started.json": "e8342394f090c3103e77f02090b26953a645b4db9380e2706968fff1d929acc3",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


@pytest.mark.parametrize("name,sha", HASHES.items())
def test_exact_original_asset_bytes(name, sha):
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha


def test_authorization_is_the_new_four_case_batch_not_spent_run_02():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["runId"] == auth["runId"] == RUN_ID
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.57"
    assert auth["manifestSha256"] == HASHES["manifest.json"]
    assert manifest["knownBefore"] == dict(e2e=31, model=80)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=35, model=92)
    assert auth["limits"] == dict(e2e=4, model=12, search=16, embedding=8,
                                  rerank=16, business=0, retry=0, resume=0)
    assert [case["caseId"] for case in manifest["cases"]] == CASE_IDS
    assert all(case["split"] == "holdout" for case in manifest["cases"])
    for name in ("consumed.json", "started.json"):
        assert read(name) == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"])


@pytest.mark.parametrize("name", [
    "agent-runtime/tests/system_e2e/knowledge_representative_uat_v3.py",
    "agent-runtime/tests/system_e2e/knowledge_representative_services_v3.py",
    "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v3.py",
    "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
    "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark.v1.json",
    "agent-runtime/src/agent_runtime/knowledge/rewrite_v9.py",
])
def test_protocol_and_sources_bound_to_frozen_commit(name):
    raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
    assert hashlib.sha256(raw).hexdigest() == read("manifest.json")["assets"][name]


def test_git_filters_preserve_original_newlines():
    for name in HASHES:
        path = (ROOT / name).relative_to(REPO).as_posix()
        raw = subprocess.check_output(["git", "hash-object", "--no-filters", path], cwd=REPO)
        filtered = subprocess.check_output(["git", "hash-object", path], cwd=REPO)
        assert raw == filtered


def test_success_and_actual_budget_are_recomputed_from_cases_and_journal():
    result = read("result.json")
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "passed" and result["failureReason"] is None
    assert result["notExecuted"] == []
    assert [row["caseId"] for row in result["cases"]] == CASE_IDS
    assert result["totals"] == dict(e2e=4, model=12, search=8, embedding=4,
                                    rerank=4, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and result["indexWrites"] == result["answer"] == 0
    for kind, count in result["totals"].items():
        assert sum(row["calls"][kind] for row in result["cases"]) == count
        assert count <= read("authorization.json")["limits"][kind]
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [event["ordinal"] for event in journal] == list(range(1, 13))
    assert [(event["caseId"], event["task"]) for event in journal] == [
        (row["caseId"], model["taskId"]) for row in result["cases"] for model in row["modelTasks"]]
    assert all(set(event) == {"caseId", "task", "ordinal", "requestSha256"} for event in journal)
    assert all(re.fullmatch(r"[0-9a-f]{64}", event["requestSha256"]) for event in journal)
    assert read("manifest.json")["knownBefore"]["e2e"] + result["totals"]["e2e"] == 35
    assert read("manifest.json")["knownBefore"]["model"] + result["totals"]["model"] == 92


def test_actual_citations_and_tasks_are_complete_but_not_manual_usefulness():
    requirements = ["vehicle_price_1", "environment_2", "stamp_price_1", "lost_invoice_1"]
    for row, requirement in zip(read("result.json")["cases"], requirements, strict=True):
        assert row["passed"] and row["httpStatus"] == 200 and row["status"] == "success"
        assert row["domains"] == (["tax.policy"] if row["caseId"] == "KRB-023" else ["tax.law"])
        assert row["taskBindingValid"] and row["retrievalComplete"]
        assert row["sourceCheck"] == dict(binding_valid=True, failure_reason=None,
                                           required_clauses=[[requirement, True]])
        assert row["validation"] == dict(phases=["coverage", "extractive"], failures=[])
        assert [(m["taskId"], m["taskVersion"]) for m in row["modelTasks"]] == [
            ("action_selection", "action-selection-v4"), ("knowledge_rewrite", "9"), ("knowledge_summary", "7")]
        assert all(m["status"] == "succeeded" and m["failureKind"] is None for m in row["modelTasks"])
        assert row["modelFailure"] == dict(records=[], overflowed=False)
        assert row["manualUsefulness"] == "not_assessed"
        for stage in ("path", "final_rank", "evidence"):
            assert row["requiredSourcesByStage"][stage] == {requirement: True}
        assert row["calls"] == dict(e2e=1, model=3, search=2, embedding=1,
                                    rerank=1, business=0, retry=0, resume=0)


def test_terminal_cleanup_and_case_events_agree():
    result = read("result.json")
    assert result["cleanup"] == [
        dict(stage="runtime_cleanup", clientsClosed=True),
        dict(stage="runtime_cleanup", clientsClosed=True),
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True),
    ]
    events = [read(f"event-{number:03d}.json") for number in range(1, 11)]
    assert [dict(stage="case", **row) for row in result["cases"]] == [
        event for event in events if event["stage"] == "case"]


def test_same_production_and_gold_as_previous_batch_without_overwriting_failure():
    old_root = ROOT.with_name("knowledge_representative_run_02")
    old = json.loads((old_root / "manifest.json").read_bytes())
    current = read("manifest.json")
    for name in ("datasetSha256", "taskVersions", "promptHashes", "qualityVersion", "indexBinding", "localModels"):
        assert old[name] == current[name]
    for prefix in ("agent-runtime/src/", "agent-service/src/", "es-query-service/src/"):
        previous = {path: sha for path, sha in old["assets"].items() if path.startswith(prefix)}
        actual = {path: sha for path, sha in current["assets"].items() if path.startswith(prefix)}
        assert previous and previous == actual
    assert current["cases"] == old["cases"][5:]
    old_result = json.loads((old_root / "result.json").read_bytes())
    assert old_result["status"] == "failed"
    assert old_result["cases"][-1]["caseId"] == "KRB-017" and not old_result["cases"][-1]["passed"]
    assert old_result["notExecuted"] == ["KRB-019", "KRB-021", "KRB-023"]
    assert current["environment"] == {
        **old["environment"], "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19401"}
    passed = [row["caseId"] for row in old_result["cases"] if row["passed"]]
    passed.extend(row["caseId"] for row in read("result.json")["cases"] if row["passed"])
    assert passed == ["KRB-006", "KRB-004", "KRB-010", "KRB-011", "KRB-012", *CASE_IDS]


def test_legacy_binding_label_resolves_to_the_frozen_actual_file():
    manifest = read("manifest.json")
    actual = "serviceCenter/knowledge-runtime-binding.v2.json"
    raw = subprocess.check_output(["git", "show", f"{HEAD}:{actual}"], cwd=REPO)
    assert manifest["assets"][actual] == manifest["assets"]["serviceCenter/knowledge-runtime-binding.v1.json"]
    assert hashlib.sha256(raw).hexdigest() == manifest["assets"][actual]


def test_finite_assets_do_not_include_questions_bodies_or_credentials():
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
