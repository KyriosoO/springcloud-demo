"""No network, no credential reads; new execution contract against frozen gold."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from tests.system_e2e import knowledge_stage_b_uat_v8 as new
from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e.test_knowledge_stage_b_citation_check_v2 import setup as sources


@pytest.fixture
def budget(tmp_path):
    with new.run_08_bindings():
        value = new.Run08Budget(tmp_path, "a" * 64, lambda row: None)
        yield value
        value.journal.close()


def request(task, question, payload=None):
    data = payload or ({"question": question, "capabilities": []} if task == "action_selection"
                       else {"question": question, "domains": []})
    prompts = dict(zip(new.TASKS, (new.ACTION_SELECTION_SYSTEM_INSTRUCTION, new.INSTRUCTION, new.summary.SUMMARY_PROMPT_V6), strict=True))
    return httpx.Request("POST", old.ModelSettings.BASE_URL + "/chat/completions", json={
        "messages": [{"role": "system", "content": prompts[task]}, {"role": "user", "content": json.dumps(data)}],
        "max_tokens": new.TOKENS[task], "response_format": {"type": "json_object"}, "tool_choice": "none"})


def summary_source(budget):
    bundle, value, points, gold = sources()
    trace = replace(bundle.question_trace, minimized_question=budget.current["question"])
    budget.bundle = replace(bundle, question_trace=trace)
    budget.summary_input = replace(value, question=budget.current["question"])
    return points, gold


def test_history_cumulative_exact_and_restored_scope():
    before = old.RUN_ID, old.CASES, old.LIMITS, old.Budget, old.run_server, old.validate_manifest
    with pytest.raises(KeyboardInterrupt), new.run_08_bindings():
        rows = new.prior_bindings()
        assert len(rows) == 7
        assert [sum(row["calls"][k] for row in rows) for k in ("e2e", "model", "search", "embedding", "rerank")] == [15, 37, 23, 12, 12]
        assert old.CASES == new.CASES and len(new.CASES) == 10
        raise KeyboardInterrupt
    assert before == (old.RUN_ID, old.CASES, old.LIMITS, old.Budget, old.run_server, old.validate_manifest)


@pytest.mark.asyncio
async def test_whole_ten_fake_cases_28_models_and_four_reranks(budget):
    for case in new.CASES:
        budget.begin(case)
        for task in tuple(new.TASKS)[:2]:
            await budget.model_request(request(task, case["question"]))
        if case["reason"]:
            continue
        summary_source(budget)
        await budget.model_request(request("knowledge_summary", case["question"], json.loads(new.summary.requirement_summary_input_json(budget.summary_input))))
        for _ in range(4):
            budget.count("rerank")
    assert budget.totals == dict(e2e=10, model=28, search=0, embedding=0, rerank=32, business=0, retry=0, resume=0)
    journal = (budget.root / "journal.jsonl").read_text()
    assert len(journal.splitlines()) == 28
    assert all(c["question"] not in journal for c in new.CASES)
    assert "合成税务" not in journal
    with pytest.raises(ValueError): budget.begin(new.CASES[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["prompt", "tokens", "tool", "schema", "question", "endpoint", "repeat"])
async def test_model_mutation_stops_before_request(budget, fault):
    budget.begin(new.CASES[0])
    req = request("action_selection", budget.current["question"])
    body = json.loads(req.content)
    if fault == "prompt": body["messages"][0]["content"] = "wrong"
    elif fault == "tokens": body["max_tokens"] = True
    elif fault == "tool": body["tools"] = [{"name": "forbidden"}]
    elif fault == "schema": body["messages"][1]["content"] = '{"question":"x","domains":[]}'
    elif fault == "question": body["messages"][1]["content"] = '{"question":"changed","capabilities":[]}'
    elif fault == "repeat": await budget.model_request(req)
    mutated = httpx.Request("POST", str(req.url) if fault != "endpoint" else "http://127.0.0.1/other", json=body)
    before = budget.totals["model"]
    with pytest.raises(ValueError, match="model_request_rejected"): await budget.model_request(mutated)
    assert budget.stopped and budget.totals["model"] == before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["schema_one", "body", "no_capture", "wrong_request"])
async def test_actual_summary_input_binding_not_reconstructed_from_payload(budget, fault):
    budget.begin(new.CASES[0])
    budget.begin(new.CASES[1])
    for task in tuple(new.TASKS)[:2]: await budget.model_request(request(task, budget.current["question"]))
    summary_source(budget)
    data = json.loads(new.summary.requirement_summary_input_json(budget.summary_input))
    if fault == "schema_one": data["schema_version"] = 1
    elif fault == "body": data["evidence"][0]["content"] = "changed"
    elif fault == "no_capture": budget.summary_input = None
    else: budget.summary_input = replace(budget.summary_input, question="other")
    with pytest.raises(ValueError): await budget.model_request(request("knowledge_summary", budget.current["question"], data))
    assert budget.totals["model"] == 2 and budget.stopped


@pytest.mark.parametrize("kind", ["model", "search", "embedding", "rerank", "business"])
def test_per_case_limit_zero_extra(budget, kind):
    budget.begin(new.CASES[0])
    for _ in range(new.PER_CASE[kind]): budget.count(kind)
    with pytest.raises(ValueError, match="budget_exceeded"): budget.count(kind)
    assert budget.totals[kind] == new.PER_CASE[kind] and budget.stopped


def test_out_of_order_and_total_budget_block(budget):
    with pytest.raises(ValueError, match="case_order_invalid"): budget.begin(new.CASES[1])
    assert budget.totals["e2e"] == 0


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    base = dict(schemaVersion=1, runId=new.RUN_ID, frozenHead="a" * 40, authorizationReference="old",
        limits=new.LIMITS, cases=new.CASES, gold=new.GOLD, environment=old.ENV, indexBinding={},
        assets={"source": "b" * 64}, executables={"jar": "c" * 64}, taskVersions={}, evaluation="original")
    monkeypatch.setattr(new.v2, "_prepare", lambda root: deepcopy(base))
    monkeypatch.setattr(old, "git", lambda *args: "")
    new.prepare(tmp_path)
    return tmp_path


def test_freeze_authorization_and_original_cases(manifest_root):
    value, sha = new.validate_manifest(manifest_root)
    assert len(value["cases"]) == 10 and value["gold"] == new.GOLD and "reusedEvidence" not in value
    assert value["schemaVersion"] == 8 and len(value["priorRuns"]) == 7
    assert value["maxOutputTokens"] == dict(action_selection=512, knowledge_rewrite=1536, knowledge_summary=1536)
    old.write_exclusive(manifest_root / "authorization.json", new.authorization(value, sha))
    environment = [dict(stage="local_model_readiness", embedding=True, rerank=True, model=0),
        dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0),
        dict(stage="runtime_cleanup", clientsClosed=True),
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]
    (manifest_root / "environment.jsonl").write_text("\n".join(json.dumps(row) for row in environment))
    assert new.validate_authorized(manifest_root, sha)[1] == sha
    with pytest.raises(FileExistsError): old.write_exclusive(manifest_root / "authorization.json", {})
    with pytest.raises(ValueError): new.prepare(manifest_root)


@pytest.mark.parametrize("fault", ["missing", "failure", "duplicate", "bad_cleanup"])
def test_bad_environment_cannot_authorize_execute(manifest_root, fault):
    value, sha = new.validate_manifest(manifest_root)
    old.write_exclusive(manifest_root / "authorization.json", new.authorization(value, sha))
    rows = [] if fault == "missing" else [dict(stage="failure", kind="RuntimeError")]
    if fault == "duplicate": rows *= 2
    if fault == "bad_cleanup": rows = [dict(stage="cleanup", ownedProcessesStopped=False, rawLogsDeleted=True, secretScanPassed=True)]
    (manifest_root / "environment.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="environment_preflight_invalid"): new.validate_authorized(manifest_root, sha)


@pytest.mark.parametrize("field,value", [("assets", {}), ("executables", {}), ("schemaVersion", 8.0), ("cases", []),
    ("priorRuns", []), ("limits", {**new.LIMITS, "model": True}), ("cumulativeLimits", {}), ("gold", {}),
    ("promptHashes", {}), ("taskVersions", {}), ("maxOutputTokens", {}), ("qualityVersion", "old"),
    ("citationCheckVersion", "v1"), ("reusedEvidence", {}), ("extra", 1)])
def test_manifest_exact_shape_and_complete_assets(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    data = json.loads(path.read_bytes())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="run_08_binding_invalid"): new.validate_manifest(manifest_root)


@pytest.mark.parametrize("name", ["result.json", "journal.jsonl", "consumed.json", "evidence.jsonl", "unknown"])
def test_partial_or_terminal_prevents_resume(manifest_root, name):
    (manifest_root / name).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"): new.validate_manifest(manifest_root)


@pytest.mark.parametrize("field,value", [("live", 1), ("frozenHead", "other"), ("manifestSha256", "b" * 64),
    ("datasetSha256", "c" * 64), ("authorizationReference", "old"), ("limits", {}), ("runId", "old")])
def test_authorization_exact_binding(manifest_root, field, value):
    manifest, sha = new.validate_manifest(manifest_root)
    auth = new.authorization(manifest, sha)
    auth[field] = value
    old.write_exclusive(manifest_root / "authorization.json", auth)
    with pytest.raises(ValueError, match="authorization_invalid"): new.validate_authorized(manifest_root, sha)


@pytest.mark.parametrize("fault", [None, "wrong_source", "missing_gold", "wrong_domain", "old_task", "old_quality"])
def test_verdict_preserves_source_domain_tasks_and_gold(budget, monkeypatch, fault):
    budget.begin(new.CASES[0]); budget.begin(new.CASES[1])
    points, gold = summary_source(budget)
    spec = {**new.CASES[1], "requiredGold": list(gold)}
    monkeypatch.setattr(new, "GOLD", gold)
    if fault == "wrong_source": points[0]["citation"]["evidenceId"] = budget.bundle.evidence[1].evidence_id
    if fault == "missing_gold": points = points[:-1]
    plans = [dict(type="knowledge_retrieval_plan", plan=dict(selected_domain_ids=["tax.policy"], quality_version=new.KNOWLEDGE_QUALITY_VERSION_V3))]
    calls = [dict(taskId=k, taskVersion=v, status="succeeded", failureKind=None) for k, v in new.TASKS.items()]
    if fault == "old_task": calls[-1]["taskVersion"] = "5"
    if fault == "old_quality": plans[0]["plan"]["quality_version"] = "old"
    if fault == "wrong_domain": plans[0]["plan"]["selected_domain_ids"] = ["tax.law"]
    value = new.assess(spec, dict(status="success", capabilityId="knowledge.query", result=dict(points=points)),
        SimpleNamespace(plans=plans, model_calls=calls, downstream_calls=[]), budget)
    assert value["passed"] is (fault is None)
    serialized = json.dumps(value)
    assert "合成税务" not in serialized and spec["question"] not in serialized


def test_clarification_requires_zero_downstream(budget):
    budget.begin(new.CASES[0])
    calls = [dict(taskId=k, taskVersion=v, status="succeeded", failureKind=None) for k, v in list(new.TASKS.items())[:2]]
    observation = SimpleNamespace(plans=[], model_calls=calls, downstream_calls=[])
    response = dict(status="no_result", capabilityId="knowledge.query", result=dict(reason="clarification_required", points=[]))
    assert new.assess(new.CASES[0], response, observation, budget)["passed"]
    observation.downstream_calls = [dict(operation="knowledge.search")]
    assert not new.assess(new.CASES[0], response, observation, budget)["passed"]


@pytest.mark.asyncio
async def test_capture_hooks_on_actual_current_production_root_and_provider_wire(budget, monkeypatch):
    from agent_runtime.capability_api.contracts import canonical_json_bytes
    from agent_runtime.model.deepseek.dto import project_deepseek_request
    from tests.integration.knowledge import test_requirement_runtime_composition as root
    original = root.Model.complete
    question = new.CASES[1]["question"]
    async def observed(self, request, **kwargs):
        wire = canonical_json_bytes(project_deepseek_request(request).payload)
        await budget.model_request(httpx.Request("POST", old.ModelSettings.BASE_URL + "/chat/completions", content=wire))
        return await original(self, request, **kwargs)
    monkeypatch.setattr(root.Model, "complete", observed)
    async def fake_server(token, emit, active):
        assert active is budget
        budget.begin(new.CASES[0]); budget.begin(new.CASES[1])
        outcome, _, clients, observation = await root.invoke(root.plan(question=question), question=question)
        assert budget.bundle is not None and budget.summary_input is not None
        from agent_runtime.capability_api.contracts import canonical_json_bytes
        points = json.loads(canonical_json_bytes(outcome.user_result))["points"]
        gold = {f"clause_{i}": dict(chunk=e.chunk_id, sha256=e.content_sha256, clause=e.content)
                for i, e in enumerate(budget.bundle.evidence, 1)}
        monkeypatch.setattr(new, "GOLD", gold)
        value = new.assess({**new.CASES[1], "requiredGold": list(gold)},
            dict(status=outcome.status.value, capabilityId=outcome.capability_id, result=dict(points=points)), observation, budget)
        assert value["passed"] and budget.totals["model"] == 3
        assert all(client.is_closed for client in clients.clients)
        return [value]
    monkeypatch.setattr(new, "_run_server", fake_server)
    build = new.summary._build_request
    select = new.DeterministicEvidenceSelector.select
    assert (await new.run_server("synthetic", lambda row: None, budget))[0]["passed"]
    assert new.summary._build_request is build and new.DeterministicEvidenceSelector.select is select


@pytest.mark.parametrize("status", [200, 503])
def test_dependency_readiness_precedes_owned_service_start(monkeypatch, status):
    from contextlib import contextmanager
    started, rows = [], []
    class Client:
        def __init__(self, **kwargs): assert kwargs["trust_env"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url):
            assert url in {"http://127.0.0.1:8908/health", "http://127.0.0.1:8909/health"}
            rows.append(url)
            return httpx.Response(status)
    @contextmanager
    def services(emit, **kwargs):
        assert len(rows) == 2
        started.append(True)
        yield "in-memory", {}
    monkeypatch.setattr(old.httpx, "Client", Client)
    monkeypatch.setattr(new, "_services", services)
    if status == 200:
        with new.checked_services(lambda row: None): assert started == [True]
    else:
        with pytest.raises(ValueError, match="local_model_not_ready"), new.checked_services(lambda row: None):
            pytest.fail("must not launch")
        assert started == []
