"""Immutable limited result and non-live diagnosis; never reconstruct model output."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

from agent_runtime.model.contracts import InvalidModelOutput
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.integration.knowledge.test_rewrite_v9_period_lookup_diagnosis import parse
from tests.system_e2e import knowledge_model_failure_probe_v2 as probe

ROOT = Path(__file__).with_name("knowledge_representative_human_run_05")
REPO = ROOT.parents[3]
HEAD = "2091aee159b54caa4902937e395519209086efd5"
HASHES = {
    "authorization.json": "20edf99b7b0ee2157392d2454cd2b60267bca77d55ff9c0aac752a335ff70577",
    "consumed.json": "8b62436c526b49071594ffd5a5bfc3693f0c89eb9a20440d74b1e415eb231a42",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "ecfce9aaf0ba22835f9e232e462e281579b892d640f3839c705aaff279a1534d",
    "event-006.json": "93b87ecdfa36c3a161652e14aa65aa33452e3eb9acbd435864d206dace20fded",
    "event-007.json": "825c93cb8a2b0bbc6ce01c4e9cfcfabf45d21397b41a91f07cc2e70ee28aaacc",
    "event-008.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-009.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "b38faa84c1e1886c49b6a02172e2eee112882b5827821de3fd48d3446f8cbaa7",
    "manifest.json": "1c49ba66979ed9c1d568bfbb57212044ca456c1d903e9d5b0cbb1a3f483e19c9",
    "result.json": "f4f353dee252cfa57e07f64621837b5556a298fb4a347d89da358d6eee134eb5",
    "started.json": "8b62436c526b49071594ffd5a5bfc3693f0c89eb9a20440d74b1e415eb231a42",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}
DIAGNOSTIC = dict(phase="rewrite_decoder", code="knowledge.invalid_requirement_plan",
                  cause="shape_or_enum", detail="unknown")


def read(name):
    return json.loads((ROOT / name).read_bytes())


def test_all_original_bytes_and_git_filters():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        path = ROOT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        args = ["git", "hash-object"]
        relative = path.relative_to(REPO).as_posix()
        assert subprocess.check_output([*args, "--no-filters", relative], cwd=REPO) == subprocess.check_output(
            [*args, relative], cwd=REPO)


def test_frozen_binding_current_source_and_protocol():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.59"
    assert auth["manifestSha256"] == HASHES["manifest.json"]
    assert manifest["limits"] == auth["limits"] == dict(e2e=9, model=27, search=36, embedding=18,
                                                       rerank=36, business=0, retry=0, resume=0)
    assert manifest["knownBefore"] == dict(e2e=37, model=97)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=46, model=124)
    names = ["agent-runtime/tests/system_e2e/" + p for p in (
        "knowledge_model_failure_probe_v2.py", "knowledge_representative_human_uat_v2.py",
        "test_knowledge_model_failure_probe_v2.py", "test_knowledge_representative_human_uat_v2.py")]
    names += ["docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
              "agent-runtime/src/agent_runtime/knowledge/rewrite_v7.py"]
    for name in names:
        raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == manifest["assets"][name]
    previous = json.loads((ROOT.with_name("knowledge_representative_human_run_04") / "manifest.json").read_bytes())
    for key in ("taskVersions", "promptHashes", "qualityVersion", "datasetSha256", "indexBinding"):
        assert previous[key] == manifest[key]


def test_terminal_budget_real_human_results_and_fail_stop():
    result, manifest = read("result.json"), read("manifest.json")
    assert result["runId"] == manifest["runId"] == "knowledge-representative-human-uat-v2-20260911-05"
    assert result["status"] == "failed" and result["failureReason"] == "execution_or_case_failed"
    assert result["totals"] == dict(e2e=3, model=8, search=4, embedding=2, rerank=3, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and result["indexWrites"] == result["answer"] == 0
    rows = result["cases"]
    assert [r["caseId"] for r in rows] == ["KRB-006", "KRB-004", "KRB-010"]
    assert result["notExecuted"] == ["KRB-011", "KRB-012", "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
    assert [c["caseId"] for c in manifest["cases"]] == [r["caseId"] for r in rows] + result["notExecuted"]
    for row in rows[:2]:
        assert row["passed"] is row["automaticPassed"] is True and row["httpStatus"] == 200
        assert row["humanReview"]["method"] == "user_interactive" and row["humanReview"]["reason"] == "none"
        assert row["humanReview"]["status"] == "assessed"
        assert all(row["humanReview"][k] is True for k in ("faithful", "relevant", "sufficientForInitialAnswer", "useful"))
        assert row["validation"] == dict(phases=["coverage", "extractive"], failures=[])
        assert row["sourceCheck"]["binding_valid"] is True
        assert all(ok is True for _, ok in row["sourceCheck"]["required_clauses"])
    failed = rows[-1]
    assert failed["passed"] is failed["automaticPassed"] is False and failed["httpStatus"] == 502
    assert failed["humanReview"] == dict(reason="automatic_failed", status="not_assessed")
    assert failed["modelFailure"] == dict(overflowed=False, records=[DIAGNOSTIC])
    assert failed["calls"] == dict(e2e=1, model=2, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    for kind, count in result["totals"].items():
        assert type(count) is int and count == sum(r["calls"][kind] for r in rows) <= manifest["limits"][kind]
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [j["ordinal"] for j in journal] == list(range(1, 9))
    assert [(j["caseId"], j["task"]) for j in journal] == [(r["caseId"], m["taskId"]) for r in rows for m in r["modelTasks"]]
    assert all(set(j) == {"caseId", "task", "ordinal", "requestSha256"} for j in journal)
    assert result["cleanup"] == [dict(stage="runtime_cleanup", clientsClosed=True)] * 2 + [
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]
    events = [read(f"event-{n:03d}.json") for n in range(1, 10)]
    assert [e for e in events if e["stage"] == "case"] == [dict(stage="case", **r) for r in rows]


def test_no_persisted_question_body_prompt_or_credentials():
    forbidden = {"question", "query", "quote", "content", "query_text", "focus", "systemInstruction",
                 "raw_response", "jwt", "apiKey", "answerSummary", "token"}
    for path in ROOT.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert not re.search(r"sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw)
        stack = [json.loads(line) for line in raw.splitlines()]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                assert not forbidden.intersection(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)


def test_known_question_is_expressible_but_shape_failure_is_not_reconstructible(monkeypatch):
    # Public frozen question, not a recovered model response or a model-generated gold.
    question = next(c.question for c in load_dataset().cases if c.id == "KRB-010")
    legal = dict(outcome="search", question_kind="lookup", queries=[dict(domain_id="tax.policy", query=question)],
                 requirements=[dict(requirement_id="r1", domain_id="tax.policy", kind="rule", focus=question)],
                 missing_conditions=[])
    assert parse(legal).outcome == "search"
    missing = deepcopy(legal)
    del missing["requirements"]
    bad_kind = deepcopy(legal)
    bad_kind["requirements"][0]["kind"] = "synthetic_unknown"
    wrong_list = {**legal, "queries": {}}
    too_many = {**legal, "queries": legal["queries"] * 3}
    for value in (missing, bad_kind, wrong_list, too_many):
        with probe.observe_failures():
            monkeypatch.setattr(probe, "_VALIDATE", lambda *a, **kw: pytest.fail("shape rejection must precede semantic validator"))
            with pytest.raises(InvalidModelOutput) as caught:
                parse(value)
            assert type(caught.value.__cause__) is ValueError
            assert asdict(probe.project_failure(caught.value)) == DIAGNOSTIC
