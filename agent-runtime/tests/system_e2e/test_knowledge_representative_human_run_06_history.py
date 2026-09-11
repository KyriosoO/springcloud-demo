"""Run-06 is immutable failure evidence, not a replayable or passing UAT."""
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
from tests.system_e2e import knowledge_model_failure_probe_v3 as probe
from tests.system_e2e.knowledge_representative_uat_v3 import strict_json

ROOT = Path(__file__).with_name("knowledge_representative_human_run_06")
REPO = ROOT.parents[3]
HEAD = "b83d877e13593ed0a6a0655cc9661ae025b665ad"
HASHES = {
    "authorization.json": "772cbc6e21dee400b68b4e56980eb2d9f78babd64a9757bf663319b10ada0ad6",
    "consumed.json": "6aa60b701a25a54c5f1cc82b60ece7b7a302d584f5c2a5e00e59f0723dd8b048",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "6e1e008330b159d921dc73e945935fa486e2524cab1fb8486a9f6a9d5b71f146",
    "event-006.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-007.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "1473c2eba71c744a575864dc2f708c1f2acd6dce15ee0d0f6c5f09dcc4d559b3",
    "manifest.json": "167325fdef1d838fd0e3388616e3f624c6b14fac0c76b1458386ff507a02ccb9",
    "result.json": "5ce04b6059af8bf99fa0fbac9e71fabd9adaaaffef5e1dac0e5090395f31ffc4",
    "started.json": "6aa60b701a25a54c5f1cc82b60ece7b7a302d584f5c2a5e00e59f0723dd8b048",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}
DIAGNOSTIC = dict(phase="rewrite_decoder", code="knowledge.invalid_requirement_plan",
                  cause="shape_or_enum", detail="root_fields")


def read(name):
    return strict_json((ROOT / name).read_bytes())


def test_original_bytes_and_git_filters():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        path = ROOT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        relative = path.relative_to(REPO).as_posix()
        assert subprocess.check_output(["git", "hash-object", "--no-filters", relative], cwd=REPO) == subprocess.check_output(
            ["git", "hash-object", relative], cwd=REPO)


def test_frozen_source_authorization_and_previous_batch_are_not_reused():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.60"
    assert auth["manifestSha256"] == HASHES["manifest.json"]
    assert manifest["limits"] == auth["limits"] == dict(e2e=7, model=21, search=28, embedding=14,
                                                       rerank=28, business=0, retry=0, resume=0)
    assert manifest["knownBefore"] == dict(e2e=40, model=105)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=47, model=126)
    assert manifest["failureDiagnostics"] == dict(version=3, details=list(probe.DETAILS))
    assert manifest["humanReview"]["required"] is True
    names = ["agent-runtime/tests/system_e2e/" + name for name in (
        "knowledge_model_failure_probe_v3.py", "knowledge_representative_human_uat_v3.py",
        "test_knowledge_model_failure_probe_v3.py", "test_knowledge_representative_human_uat_v3.py")]
    names += ["docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
              "agent-runtime/src/agent_runtime/knowledge/rewrite_v7.py",
              "agent-runtime/src/agent_runtime/knowledge/rewrite_v9.py"]
    for name in names:
        raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == manifest["assets"][name]
    previous = strict_json((ROOT.with_name("knowledge_representative_human_run_05") / "manifest.json").read_bytes())
    for key in ("taskVersions", "promptHashes", "qualityVersion", "datasetSha256", "indexBinding"):
        assert manifest[key] == previous[key]


def test_terminal_counts_journal_fail_stop_and_cleanup():
    result, manifest, auth = read("result.json"), read("manifest.json"), read("authorization.json")
    assert result["runId"] == manifest["runId"] == auth["runId"] == "knowledge-representative-human-uat-v3-20260911-06"
    assert result["manifestSha256"] == HASHES["manifest.json"]
    for name in ("started.json", "consumed.json"):
        assert read(name) == dict(runId=result["runId"], manifestSha256=HASHES["manifest.json"])
    assert result["status"] == "failed" and result["failureReason"] == "execution_or_case_failed"
    assert result["totals"] == dict(e2e=1, model=2, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and read("warmup-attempt.json") == dict(rerank=1)
    assert result["indexWrites"] == result["answer"] == 0
    assert len(result["cases"]) == 1
    row = result["cases"][0]
    assert row["caseId"] == "KRB-010" and row["calls"] == result["totals"]
    assert row["passed"] is row["automaticPassed"] is False and row["httpStatus"] == 502
    assert row["humanReview"] == dict(reason="automatic_failed", status="not_assessed")
    assert row["manualUsefulness"] == "not_assessed"
    assert row["status"] == "downstream_failure" and row["planSha256"] is None
    assert row["modelFailure"] == dict(overflowed=False, records=[DIAGNOSTIC])
    assert row["validation"] == dict(phases=[], failures=[])
    assert row["domains"] == row["retrievalStages"] == row["evidenceContentHashes"] == []
    assert row["sourceCheck"] is None and row["retrievalComplete"] is False
    assert row["modelTasks"] == [
        dict(taskId="action_selection", taskVersion="action-selection-v4", status="succeeded", failureKind=None),
        dict(taskId="knowledge_rewrite", taskVersion="9", status="failed", failureKind="invalid_output")]
    assert result["notExecuted"] == ["KRB-011", "KRB-012", "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
    assert [c["caseId"] for c in manifest["cases"]] == [row["caseId"], *result["notExecuted"]]
    for kind, count in result["totals"].items():
        assert type(count) is int and count <= manifest["limits"][kind]
    journal = [strict_json(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [j["ordinal"] for j in journal] == [1, 2]
    assert [(j["caseId"], j["task"]) for j in journal] == [(row["caseId"], m["taskId"]) for m in row["modelTasks"]]
    assert all(set(j) == {"caseId", "task", "ordinal", "requestSha256"} for j in journal)
    assert result["cleanup"] == [dict(stage="runtime_cleanup", clientsClosed=True)] * 2 + [
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]
    events = [read(f"event-{n:03d}.json") for n in range(1, 8)]
    assert [e for e in events if e["stage"] == "case"] == [dict(stage="case", **row)]


def test_no_persisted_model_content_questions_or_credentials():
    forbidden = {"question", "query", "quote", "content", "query_text", "focus", "systemInstruction",
                 "raw_response", "jwt", "apiKey", "answerSummary", "token"}
    questions = [case.question for case in load_dataset().cases]
    for path in ROOT.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert not re.search(r"sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw)
        assert not any(question in raw or json.dumps(question)[1:-1] in raw for question in questions)
        stack = [strict_json(line.encode()) for line in raw.splitlines()]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                assert not forbidden.intersection(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)


@pytest.mark.parametrize("missing", ["outcome", "question_kind", "queries", "requirements", "missing_conditions"])
def test_root_fields_does_not_identify_actual_missing_or_extra_field(missing):
    # Synthetic counterexamples, never a reconstruction of the live model response.
    question = next(c.question for c in load_dataset().cases if c.id == "KRB-010")
    legal = dict(outcome="search", question_kind="lookup", queries=[dict(domain_id="tax.policy", query=question)],
                 requirements=[dict(requirement_id="r1", domain_id="tax.policy", kind="rule", focus=question)],
                 missing_conditions=[])
    assert parse(legal).outcome == "search"
    omitted = deepcopy(legal)
    del omitted[missing]
    renamed = {**omitted, "synthetic_unknown": legal[missing]}
    for value in (omitted, renamed, {**legal, "synthetic_unknown": None}):
        with probe.observe_failures():
            with pytest.raises(InvalidModelOutput) as caught:
                parse(value)
            assert asdict(probe.project_failure(caught.value)) == DIAGNOSTIC
