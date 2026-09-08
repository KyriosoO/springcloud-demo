"""Run-09 protocol counterexamples; no credentials or network needed."""
from contextlib import contextmanager
from copy import deepcopy
import json

import pytest

from tests.system_e2e import knowledge_stage_b_uat_v9 as new
from tests.system_e2e import test_knowledge_stage_b_uat_v8 as checks


@pytest.fixture(autouse=True)
def scoped(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with new.bindings():
        yield


@pytest.fixture
def budget(tmp_path):
    value = new.Run09Budget(tmp_path, "a" * 64, lambda row: None)
    yield value
    value.journal.close()


def test_history_eight_original_failures_and_exact_budget():
    rows = new.prior_bindings()
    assert len(rows) == 8
    assert {k: sum(r["calls"][k] for r in rows) for k in new.LIMITS} == dict(
        e2e=16, model=39, search=27, embedding=14, rerank=14, business=0, retry=0, resume=0)
    assert new.TOTAL_LIMITS["model"] == 67 and new.TOTAL_LIMITS["e2e"] == 26
    assert 14 + new.LIMITS["rerank"] + new.STARTUP_LIMITS["rerank"] == 47


def test_scope_restores_on_exception():
    before = (new.previous.RUN_ID, new.legacy.Budget, new.legacy.run_server, new.previous.INSTRUCTION)
    with pytest.raises(KeyboardInterrupt), new.bindings({"test": True}):
        assert new._active_manifest == {"test": True}
        raise KeyboardInterrupt
    assert before == (new.previous.RUN_ID, new.legacy.Budget, new.legacy.run_server, new.previous.INSTRUCTION)
    assert new._active_manifest is None


@pytest.mark.asyncio
async def test_whole_original_ten_exact_maximum_budget(budget):
    for case in new.CASES:
        budget.begin(case)
        for task in tuple(new.TASKS)[:2]:
            await budget.model_request(checks.request(task, case["question"]))
        if not case["reason"]:
            checks.summary_source(budget)
            await budget.model_request(checks.request("knowledge_summary", case["question"], json.loads(
                new.previous.summary.requirement_summary_input_json(budget.summary_input))))
            for kind, count in (("search", 4), ("embedding", 2), ("rerank", 4)):
                for _ in range(count): budget.count(kind)
    assert budget.totals == new.LIMITS
    journal = (budget.root / "journal.jsonl").read_text()
    assert len(journal.splitlines()) == 28
    assert all(c["question"] not in journal for c in new.CASES)
    assert "合成税务" not in journal
    consumed = json.loads((budget.root / "consumed.json").read_bytes())
    assert consumed["runId"] == new.RUN_ID
    with pytest.raises(ValueError): budget.begin(new.CASES[0])


@pytest.mark.parametrize("kind", ["model", "search", "embedding", "rerank", "business"])
def test_clarification_zero_downstream_before_outbound(budget, kind):
    budget.begin(new.CASES[0])
    if kind == "model":
        budget.count(kind); budget.count(kind)
    before = dict(budget.totals)
    with pytest.raises(ValueError, match="clarification_outbound_rejected"): budget.count(kind)
    assert budget.stopped and budget.totals == before


@pytest.mark.parametrize("kind", ["model", "search", "embedding", "rerank", "business"])
def test_per_case_and_total_limits(budget, kind):
    budget.begin(new.CASES[0]); budget.begin(new.CASES[1])
    for _ in range(new.previous.PER_CASE[kind]): budget.count(kind)
    with pytest.raises(ValueError, match="budget_exceeded"): budget.count(kind)
    assert budget.stopped


@pytest.mark.parametrize("kind", ["model", "search", "embedding", "rerank"])
def test_total_budget_blocks_before_attempt(budget, kind):
    budget.begin(new.CASES[0]); budget.begin(new.CASES[1])
    budget.totals[kind] = new.LIMITS[kind]
    with pytest.raises(ValueError, match="budget_exceeded"): budget.count(kind)
    assert budget.totals[kind] == new.LIMITS[kind] and budget.per_case[kind] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["prompt", "tokens", "tool", "schema", "question", "endpoint", "repeat"])
async def test_model_contract_rejects_mutation(budget, fault):
    await checks.test_model_mutation_stops_before_request(budget, fault)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["schema_one", "body", "no_capture", "wrong_request"])
async def test_summary_bound_to_actual_original_evidence(budget, fault):
    await checks.test_actual_summary_input_binding_not_reconstructed_from_payload(budget, fault)


@pytest.mark.parametrize("fault", [None, "wrong_source", "missing_gold", "wrong_domain", "old_task", "old_quality"])
def test_original_source_and_gold_not_weakened(budget, monkeypatch, fault):
    checks.test_verdict_preserves_source_domain_tasks_and_gold(budget, monkeypatch, fault)


@pytest.mark.asyncio
async def test_current_root_capture_provider_wire_and_context_observer(budget, monkeypatch):
    before = new.ContextualBgeRerankAdapter.rerank
    # Reuse the original real production-root fake test, but enter the new context observer too.
    original_test_entry = new.previous.run_server
    assert original_test_entry is new.run_server
    await checks.test_capture_hooks_on_actual_current_production_root_and_provider_wire(budget, monkeypatch)
    ranks = [r for r in budget.probes if r["stage"] == "rerank"]
    assert len(ranks) == 3 and all(r["inputVersion"] == new.ContextualBgeRerankAdapter.INPUT_VERSION for r in ranks)
    assert new.ContextualBgeRerankAdapter.rerank is before
    assert "合成税务" not in json.dumps(ranks)


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    base = dict(schemaVersion=1, runId=new.RUN_ID, frozenHead="a" * 40, authorizationReference="old",
        limits=new.LIMITS, cases=new.CASES, gold=new.GOLD, environment=new.legacy.ENV, indexBinding={},
        assets={"source": "b" * 64}, executables={"jar": "c" * 64}, taskVersions={}, evaluation="original")
    monkeypatch.setattr(new.previous.v2, "_prepare", lambda root: deepcopy(base))
    monkeypatch.setattr(new.legacy, "git", lambda *args: "")
    monkeypatch.setattr(new.probe, "local_models", lambda: {"fake": {"containerId": "f" * 64, "imageId": "sha256:" + "d" * 64}})
    new.previous.prepare(tmp_path)
    return tmp_path


def environment_rows():
    return [dict(stage="local_model_readiness", embedding=True, rerank=True, model=0),
            dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0),
            dict(stage="runtime_cleanup", clientsClosed=True), dict(stage="final_binding", unchanged=True),
            dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]


def preflight(root, sha):
    rows = [dict(stage="warmup_attempt", runId=new.RUN_ID, manifestSha256=sha, rerank=1, model=0),
            dict(stage="warmup_ready", rerank=1, items=40, clientsClosed=True)]
    (root / "startup.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (root / "environment.jsonl").write_text("\n".join(json.dumps(r) for r in environment_rows()))


def test_manifest_actual_binding_new_tasks_and_authorization(manifest_root):
    manifest, sha = new.validate_manifest(manifest_root)
    assert manifest["schemaVersion"] == 9 and len(manifest["priorRuns"]) == 8
    assert manifest["cases"] == list(new.CASES) and manifest["gold"] == new.GOLD
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="8", summary="6")
    assert manifest["indexBinding"]["expectedIndexUuid"] == "jJ5Ww3LCRWWycfDkUZvmdw"
    assert manifest["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    for name in (new.BINDING, new.WARMUP):
        assert manifest["assets"][name] == new.legacy.digest((new.legacy.REPO / name).read_bytes())
    preflight(manifest_root, sha)
    new.legacy.write_exclusive(manifest_root / "authorization.json", new.authorization(manifest, sha))
    assert new.validate_authorized(manifest_root, sha)[1] == sha
    with pytest.raises(FileExistsError): new.legacy.write_exclusive(manifest_root / "authorization.json", {})
    with pytest.raises(ValueError): new.previous.prepare(manifest_root)


@pytest.mark.parametrize("field,value", [("assets", {}), ("executables", {}), ("schemaVersion", 9.0), ("cases", []),
    ("priorRuns", []), ("limits", {**new.LIMITS, "model": True}), ("cumulativeLimits", {}), ("gold", {}),
    ("promptHashes", {}), ("taskVersions", {}), ("maxOutputTokens", {}), ("qualityVersion", "old"),
    ("citationCheckVersion", "v1"), ("reusedEvidence", {}), ("extra", 1), ("startupLimits", {"rerank": True}),
    ("localModels", {}), ("indexBinding", {}), ("rerankInputVersion", "raw-content-v1")])
def test_manifest_exact_complete_asset_set(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    data = json.loads(path.read_bytes()); data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="run_09_binding_invalid"): new.validate_manifest(manifest_root)


@pytest.mark.parametrize("name", ["result.json", "journal.jsonl", "consumed.json", "evidence.jsonl", "unknown"])
def test_partial_or_terminal_never_resumes(manifest_root, name):
    (manifest_root / name).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"): new.validate_manifest(manifest_root)


@pytest.mark.parametrize("fault", ["missing", "failed", "duplicate", "bad_cleanup", "bool_count"])
def test_bad_preflight_cannot_authorize(manifest_root, fault):
    manifest, sha = new.validate_manifest(manifest_root)
    preflight(manifest_root, sha)
    if fault == "bool_count":
        path = manifest_root / "startup.jsonl"
        path.write_text(path.read_text().replace('"rerank": 1', '"rerank": true'))
    else:
        rows = environment_rows()
        if fault == "missing": rows.pop()
        elif fault == "failed": rows.append(dict(stage="failure", kind="RuntimeError"))
        elif fault == "duplicate": rows.append(rows[0])
        else: rows[-1]["ownedProcessesStopped"] = False
        (manifest_root / "environment.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError): new.authorization(manifest, sha)
    assert not (manifest_root / "authorization.json").exists()


@pytest.mark.parametrize("field,value", [("live", 1), ("frozenHead", "other"), ("manifestSha256", "b" * 64),
    ("datasetSha256", "c" * 64), ("authorizationReference", "old"), ("limits", {}), ("runId", "old"),
    ("startupLimits", {}), ("startupSha256", "e" * 64), ("environmentSha256", "e" * 64)])
def test_authorization_exact_binding(manifest_root, field, value):
    manifest, sha = new.validate_manifest(manifest_root); preflight(manifest_root, sha)
    auth = new.authorization(manifest, sha); auth[field] = value
    new.legacy.write_exclusive(manifest_root / "authorization.json", auth)
    with pytest.raises(ValueError, match="authorization_invalid"): new.validate_authorized(manifest_root, sha)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "raise", "bad_response"])
async def test_warmup_exclusive_attempt_precedes_single_call(tmp_path, monkeypatch, fault):
    calls = []
    monkeypatch.setattr(new, "assert_environment", lambda: None)
    async def warmup():
        rows = [json.loads(line) for line in (tmp_path / "startup.jsonl").read_bytes().splitlines()]
        assert len(rows) == 1 and rows[0]["stage"] == "warmup_attempt"
        calls.append(1)
        if fault == "raise": raise ValueError("synthetic secret not to persist")
        return dict(status="ready", rerankCalls=True if fault == "bad_response" else 1, items=40, clientClosed=True)
    monkeypatch.setattr(new, "_warmup", warmup)
    if fault:
        with pytest.raises(SystemExit, match="startup_failed"): await new.warmup_once(tmp_path, "a" * 64)
        with pytest.raises(ValueError): new.validate_startup(tmp_path, "a" * 64)
    else:
        await new.warmup_once(tmp_path, "a" * 64)
        new.validate_startup(tmp_path, "a" * 64)
    with pytest.raises(FileExistsError): await new.warmup_once(tmp_path, "a" * 64)
    assert calls == [1] and "synthetic secret" not in (tmp_path / "startup.jsonl").read_text()


def test_service_binding_redirect_is_exact_and_restored(monkeypatch):
    before = new.services.REPO
    manifest = {"runRoot": "synthetic"}
    monkeypatch.setattr(new, "_active_manifest", manifest)
    checks_seen, rows = [], []
    monkeypatch.setattr(new, "assert_environment", lambda: checks_seen.append(True))
    monkeypatch.setattr(new, "current_manifest", lambda root: manifest)
    @contextmanager
    def service(emit, **kwargs):
        assert new.services.REPO / "serviceCenter/knowledge-runtime-binding.v1.json" == new.legacy.REPO / new.BINDING
        assert new.services.REPO / "auth-service" == new.legacy.REPO / "auth-service"
        yield "synthetic", {}
    monkeypatch.setattr(new, "_checked_services", service)
    with pytest.raises(KeyboardInterrupt), new.checked_services(rows.append):
        raise KeyboardInterrupt
    assert new.services.REPO is before and checks_seen == [True, True]
    assert rows == [dict(stage="final_binding", unchanged=True)]


def test_changed_model_identity_stops_before_index_read(monkeypatch):
    monkeypatch.setattr(new, "_active_manifest", {"localModels": {"frozen": 1}})
    monkeypatch.setattr(new.probe, "local_models", lambda: {"changed": 1})
    monkeypatch.setattr(new.probe, "check_index", lambda *args: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="local_models_changed"): new.assert_environment()


def test_cli_phases_warmup_only_once_and_consumption_blocks_resume(manifest_root, monkeypatch):
    _, sha = new.validate_manifest(manifest_root)
    calls = []
    monkeypatch.setattr(new, "assert_environment", lambda: None)
    async def warmup():
        calls.append("warmup")
        return dict(status="ready", rerankCalls=1, items=40, clientClosed=True)
    monkeypatch.setattr(new, "_warmup", warmup)
    def legacy_main():
        mode = new.sys.argv[1]
        assert new._active_manifest["taskVersions"]["rewrite"] == "8"
        calls.append(mode)
        if mode == "check-environment":
            (manifest_root / "environment.jsonl").write_text("\n".join(json.dumps(r) for r in environment_rows()))
        else:
            new.legacy.validate_manifest(manifest_root, sha)
            (manifest_root / "journal.jsonl").touch()
    monkeypatch.setattr(new.legacy, "main", legacy_main)
    def invoke(mode):
        monkeypatch.setattr(new.sys, "argv", ["new-runner", mode, "--root", str(manifest_root), "--manifest-sha256", sha])
        new.main()
    invoke("check-environment")
    invoke("authorize")
    invoke("execute")
    assert calls == ["warmup", "check-environment", "execute"]
    with pytest.raises(ValueError, match="retry_resume_forbidden"): invoke("execute")
    assert calls == ["warmup", "check-environment", "execute"]


@pytest.mark.parametrize("raw", ['{"schemaVersion":9,"schemaVersion":9}', '{"schemaVersion":NaN}'])
def test_duplicate_and_nonfinite_manifest_rejected(manifest_root, raw):
    (manifest_root / "manifest.json").write_text(raw)
    with pytest.raises(ValueError): new.validate_manifest(manifest_root)
