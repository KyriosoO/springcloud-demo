"""Freeze real human evidence and domain-contract failure without replaying a run."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10, OUTPUT_NAME
from agent_runtime.model.contracts import (
    InvalidModelOutput, StructuredFinishKind, StructuredModelResponse, StructuredToolCall,
)
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_model_failure_probe_v3 as probe
from tests.system_e2e import knowledge_representative_human_uat_v4 as runner

ROOT = Path(__file__).with_name("knowledge_representative_human_run_07")
REPO = ROOT.parents[3]
HEAD = "8e34893ffb4b67e34bddccde231999c0734eb2af"
HASHES = {
    "authorization.json": "d134eeb8e61cf0148df20939e928a7889be6ca87a4101cadb3ed5add6a903c2a",
    "consumed.json": "1eb5e6af9db0784780e319cee4cfcf2db65466c46e1adb2011c66a9894a005e2",
    "event-001.json": "5a79132c7a80b16ffc0ec6fead32b3ff36291200698fdcdf44097640f75703fd",
    "event-002.json": "efe7a41fdbf73f425070b67c392d2d7880cf375ede5e7a0a909380fcb95d68b7",
    "event-003.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-004.json": "60b352f80fc3ec124225e7b2f4cba9a6ecbdd66d31a055fbf01b3911513a49b5",
    "event-005.json": "93bfc82853885fa68af9c14974ba1de63a826434b9fe226a772d99f783d1dc06",
    "event-006.json": "a1b9acc581a110a7faa7768fb64c257c6446aa1249f78cb7f2edde4fa7cca8b7",
    "event-007.json": "218314575875ae730d3b04670a04ef2e207d4aab2e9b3832ff92162fd6f5ca3a",
    "event-008.json": "b11bcb6eaedb7be1909332dca15aee8c83ab67bd0627e77153e03846d55b6f4f",
    "journal.jsonl": "a095dc22e66ab9469b061b353909be319d71a37cb9d0f0bc5b43b3a50ff09511",
    "manifest.json": "4b8334ece35d08a9db81fd33067db5635436708bf18ae70ea11f88b3b374db28",
    "result.json": "915724a415d10605d336f8c24139fc7dd2f51e4520f5df211099736a1ba0b69e",
    "started.json": "1eb5e6af9db0784780e319cee4cfcf2db65466c46e1adb2011c66a9894a005e2",
    "warmup-attempt.json": "cdb5ab0bfc00b83c5e36a902c40b53dad0f596ab75c460590fd5ad36cccc32a3",
}
DIAGNOSTIC = dict(phase="rewrite_decoder", code="knowledge.invalid_requirement_plan",
                  cause="semantic_contract", detail="domains")


def read(name):
    return runner.base.strict_json((ROOT / name).read_bytes())


def test_original_bytes_and_git_filters():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        path = ROOT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        relative = path.relative_to(REPO).as_posix()
        assert subprocess.check_output(["git", "hash-object", "--no-filters", relative], cwd=REPO) == subprocess.check_output(
            ["git", "hash-object", relative], cwd=REPO)


def test_frozen_source_and_fresh_model_protocol_are_not_old_passes():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert manifest["frozenHead"] == auth["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == auth["reference"] == "UAT_01:14.62"
    assert auth["manifestSha256"] == HASHES["manifest.json"]
    assert manifest["limits"] == auth["limits"] == dict(e2e=10, model=30, search=40, embedding=20,
                                                       rerank=40, business=0, retry=0, resume=0)
    assert manifest["knownBefore"] == dict(e2e=41, model=107)
    assert manifest["cumulativeLimits"] == auth["cumulativeLimits"] == dict(e2e=51, model=137)
    assert manifest["taskVersions"] == dict(action_selection="action-selection-v4", knowledge_rewrite="10", knowledge_summary="7")
    assert manifest["modelWire"] == dict(model="deepseek-flash", rewritePath="/beta/chat/completions",
        otherTaskPath="/chat/completions", outputToolsSha256="f9ac98b9d88edb2f54554e8b2c93dfdbbbec7c77556d8e87bc8a49e8a3cf3358")
    assert manifest["humanReview"]["required"] is True
    names = ["agent-runtime/tests/system_e2e/" + name for name in (
        "knowledge_model_failure_probe_v3.py", "knowledge_representative_human_uat_v4.py",
        "test_knowledge_model_failure_probe_v3.py", "test_knowledge_representative_human_uat_v4.py")]
    names += ["docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md",
        "agent-runtime/src/agent_runtime/bootstrap.py", "agent-runtime/src/agent_runtime/knowledge/rewrite_v10.py",
        "agent-runtime/src/agent_runtime/knowledge/rewrite_v7.py", "agent-runtime/src/agent_runtime/model/settings.py",
        "agent-runtime/src/agent_runtime/model/deepseek/dto.py", "agent-runtime/src/agent_runtime/model/deepseek/transport.py"]
    for name in names:
        raw = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == manifest["assets"][name]
    previous = runner.base.strict_json((ROOT.with_name("knowledge_representative_human_run_06") / "manifest.json").read_bytes())
    assert previous["taskVersions"]["knowledge_rewrite"] == "9"
    assert previous["promptHashes"]["knowledge_rewrite"] != manifest["promptHashes"]["knowledge_rewrite"]
    for key in ("qualityVersion", "datasetSha256", "indexBinding"):
        assert previous[key] == manifest[key]


def test_real_human_pass_and_failed_case_remain_separate():
    result = read("result.json")
    assert set(result) == {"runId", "manifestSha256", "status", "startupRerank", "indexWrites", "answer",
                           "failureReason", "cases", "totals", "notExecuted", "cleanup"}
    assert result["status"] == "failed" and result["failureReason"] == "execution_or_case_failed"
    passed, failed = result["cases"]
    assert passed["caseId"] == "KRB-015" and passed["httpStatus"] == 200
    assert passed["passed"] is passed["automaticPassed"] is True
    assert passed["manualUsefulness"] == "passed" and passed["taskBindingValid"] is True
    assert passed["humanReview"]["method"] == "user_interactive"
    assert passed["humanReview"]["status"] == "assessed" and passed["humanReview"]["reason"] == "none"
    assert all(passed["humanReview"][k] is True for k in ("faithful", "relevant", "sufficientForInitialAnswer", "useful"))
    assert passed["validation"] == dict(phases=["coverage", "extractive"], failures=[])
    assert passed["sourceCheck"]["binding_valid"] is passed["retrievalComplete"] is True
    assert passed["domains"] == ["tax.policy", "tax.law"]
    assert all(all(sources.values()) for sources in passed["requiredSourcesByStage"].values())
    assert passed["modelFailure"] == dict(overflowed=False, records=[])
    assert failed["caseId"] == "KRB-006" and failed["httpStatus"] == 502
    assert failed["status"] == "downstream_failure" and failed["passed"] is failed["automaticPassed"] is False
    assert failed["humanReview"] == dict(reason="automatic_failed", status="not_assessed")
    assert failed["manualUsefulness"] == "not_assessed" and failed["planSha256"] is None
    assert failed["modelFailure"] == dict(overflowed=False, records=[DIAGNOSTIC])
    assert failed["domains"] == failed["retrievalStages"] == failed["evidenceContentHashes"] == []
    assert failed["sourceCheck"] is None and failed["retrievalComplete"] is False
    assert failed["validation"] == dict(phases=[], failures=[])
    assert [(t["taskId"], t["taskVersion"], t["status"]) for t in failed["modelTasks"]] == [
        ("action_selection", "action-selection-v4", "succeeded"), ("knowledge_rewrite", "10", "failed")]
    assert failed["modelTasks"][1]["failureKind"] == "invalid_output"
    assert not any(failed["calls"][k] for k in ("search", "embedding", "rerank", "business", "retry", "resume"))


def test_terminal_budget_journal_order_cleanup_and_no_resume(monkeypatch):
    result, manifest = read("result.json"), read("manifest.json")
    assert result["runId"] == manifest["runId"] == read("authorization.json")["runId"] == runner.RUN_ID
    assert result["manifestSha256"] == HASHES["manifest.json"]
    assert result["totals"] == dict(e2e=2, model=5, search=4, embedding=2, rerank=2, business=0, retry=0, resume=0)
    assert result["startupRerank"] == 1 and read("warmup-attempt.json") == dict(rerank=1)
    assert result["indexWrites"] == result["answer"] == 0
    assert result["notExecuted"] == ["KRB-004", "KRB-010", "KRB-011", "KRB-012", "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
    assert [c["caseId"] for c in manifest["cases"]] == [r["caseId"] for r in result["cases"]] + result["notExecuted"]
    for kind, count in result["totals"].items():
        assert type(count) is int and count <= manifest["limits"][kind]
        assert count == sum(row["calls"][kind] for row in result["cases"])
        assert all(type(row["calls"][kind]) is int for row in result["cases"])
    for name in ("started.json", "consumed.json"):
        assert read(name) == dict(runId=result["runId"], manifestSha256=HASHES["manifest.json"])
    journal = [runner.base.strict_json(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert [j["ordinal"] for j in journal] == [1, 2, 3, 4, 5]
    assert [(j["caseId"], j["task"]) for j in journal] == [
        (row["caseId"], task["taskId"]) for row in result["cases"] for task in row["modelTasks"]]
    assert all(set(j) == {"caseId", "task", "ordinal", "requestSha256"} for j in journal)
    assert result["cleanup"] == [dict(stage="runtime_cleanup", clientsClosed=True)] * 2 + [
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]
    events = [read(f"event-{n:03d}.json") for n in range(1, 9)]
    assert [e for e in events if e["stage"] == "case"] == [dict(stage="case", **r) for r in result["cases"]]
    monkeypatch.setattr(runner, "ROOT", ROOT)
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        runner.validate_frozen(HASHES["manifest.json"])


def test_no_persisted_model_content_questions_or_credentials():
    forbidden = {"question", "query", "quote", "content", "query_text", "focus", "systemInstruction",
                 "raw_response", "jwt", "apiKey", "answerSummary", "token"}
    questions = [case.question for case in load_dataset().cases]
    for path in ROOT.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert not re.search(r"sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw)
        assert not any(question in raw or json.dumps(question)[1:-1] in raw for question in questions)
        stack = [runner.base.strict_json(line.encode()) for line in raw.splitlines()]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                assert not forbidden.intersection(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)


@pytest.mark.parametrize("variant", ["duplicate", "unknown", "wrong_type"])
def test_finite_domains_reason_does_not_reconstruct_the_actual_response(variant):
    # Synthetic counterexamples to demonstrate the recorded reason's ambiguity.
    legal = dict(outcome="search", question_kind="lookup", queries=[dict(domain_id="tax.policy", query="税务政策规则")],
        requirements=[dict(requirement_id="r1", domain_id="tax.policy", kind="rule", focus="税务政策规则")], missing_conditions=[])
    def parse(value):
        return KnowledgeRewriteTaskV10.definition().parse_response(StructuredModelResponse(
            finish_kind=StructuredFinishKind.TOOL_CALLS, content=None, usage_total_tokens=0,
            tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps(value)),)))
    assert parse(legal).outcome == "search"
    rejected = deepcopy(legal)
    if variant == "duplicate":
        rejected["queries"].append(dict(rejected["queries"][0]))
    else:
        rejected["queries"][0]["domain_id"] = "synthetic.unknown" if variant == "unknown" else 1
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput) as caught:
            parse(rejected)
        assert asdict(probe.project_failure(caught.value)) == DIAGNOSTIC
