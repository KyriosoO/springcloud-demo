"""The comparison cannot silently change the corpus, models or production config."""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from tests.system_e2e import knowledge_document_number_benchmark_v1 as runner


def test_only_owned_es_child_gets_fixed_flag_without_global_patch():
    calls = []
    popen = lambda command, **kwargs: calls.append((command, kwargs)) or object()
    original = SimpleNamespace(Popen=popen, TimeoutExpired=TimeoutError, STDOUT=-1, CREATE_NO_WINDOW=1)
    support = SimpleNamespace(subprocess=original)
    state = {"profileFlagLaunches": 0}
    assert runner.configured_support(support, state) is support
    env = {"COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": "synthetic-key"}
    auth = ["java", "-jar", "auth.jar", "--server.port=18090"]
    support.subprocess.Popen(auth, cwd=runner.base.REPO / "auth-service", env=env)
    command = ["java", "-cp", "synthetic", runner.MAIN_CLASS, "--server.port=19201"]
    support.subprocess.Popen(command, cwd=runner.base.REPO / "es-query-service", env=env)
    assert calls[0][0] == auth and calls[1][0] == [*command, runner.FLAG]
    assert calls[1][1]["env"] is env and original.Popen is popen
    assert support.subprocess.TimeoutExpired is TimeoutError
    assert runner.FLAG not in command and state["profileFlagLaunches"] == 1
    with pytest.raises(ValueError, match="probe_outbound_rejected"):
        support.subprocess.Popen(command, cwd=runner.base.REPO / "es-query-service")
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ["cwd", "port", "duplicate", "override", "shell"])
def test_ambiguous_process_launch_rejected_before_popen(fault):
    calls = []
    support = SimpleNamespace(subprocess=SimpleNamespace(Popen=lambda *a, **kw: calls.append(a)))
    runner.configured_support(support, {"profileFlagLaunches": 0})
    command = ["java", runner.MAIN_CLASS, "--server.port=19201"]
    cwd = runner.base.REPO / "es-query-service"
    if fault == "cwd": cwd = runner.base.REPO
    elif fault == "port": command[-1] = "--server.port=9201"
    elif fault == "duplicate": command.append(runner.MAIN_CLASS)
    elif fault == "override": command.append(runner.FLAG)
    else: command = "java " + runner.MAIN_CLASS
    with pytest.raises(ValueError, match="probe_outbound_rejected"):
        support.subprocess.Popen(command, cwd=cwd)
    assert calls == []


@pytest.mark.parametrize("key", ["bindingSha256", "catalogSha256", "fixtureSha256", "caseIds", "budgets",
                               "localModelContainers", "datasetSha256", "rerankInputVersion", "artifact"])
def test_prepared_comparison_rejects_baseline_drift(key):
    baseline = runner.load_baseline()
    value = deepcopy(baseline)
    runner.validate_prepared(value, baseline)
    # New service implementation is the intended independent variable.
    value["artifactHashes"]["es-query-service/target/classes/com/dylan/esquery/service/KnowledgeSearchService.class"] = "a" * 64
    runner.validate_prepared(value, baseline)
    if key == "artifact": value["artifactHashes"][runner.STABLE_ARTIFACTS[0]] = "changed"
    else: value[key] = "changed"
    with pytest.raises(ValueError, match="probe_artifacts_changed"):
        runner.validate_prepared(value, baseline)


@pytest.mark.parametrize("value,allowed", [({}, False), ({"defaults": {"search": {"allow_expensive_queries": "false"}}}, False),
    ({"defaults": {"search": {"allow_expensive_queries": "true"}}, "persistent": {"search": {"allow_expensive_queries": False}}}, False),
    ({"persistent": {"search": {"allow_expensive_queries": "false"}}, "transient": {"search": {"allow_expensive_queries": "true"}}}, True),
    ({"defaults": {"search": {"allow_expensive_queries": "true"}}}, True),
    ({"persistent": {"search": {"allow_expensive_queries": "unknown"}}}, False),
    ({"defaults": {"search.allow_expensive_queries": "true"}}, False),
    ({"defaults": []}, False), ({"defaults": {"search": None}}, False), ([], False)])
def test_cluster_settings_precedence_without_relaxing_cluster(value, allowed):
    assert runner.expensive_queries_allowed(value) is allowed


@pytest.mark.parametrize("fault", [False, True])
def test_wrapper_reuses_benchmark_and_restores_on_success_or_failure(monkeypatch, tmp_path, fault):
    base = runner.base
    original = base.load_support, base.artifact_hashes, base.check_index, base.emit_line, base.ObservedSearch
    baseline = runner.load_baseline()
    emitted, reads, started = [], [], []
    for relative in runner.EXTRA_CLASSES:
        path = tmp_path / "es-query-service/target/classes/com/dylan/esquery" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic compiled class")
    monkeypatch.setattr(base, "REPO", tmp_path)
    monkeypatch.setattr(base, "artifact_hashes", lambda: dict(baseline["artifactHashes"]))
    monkeypatch.setattr(base, "check_index", lambda *a: reads.append("index"))
    monkeypatch.setattr(base, "emit_line", lambda stream, value: emitted.append(value))
    def request(client, method, url):
        assert method == "GET" and "flat_settings=false" in url
        reads.append(method)
        return 200, b'{"defaults":{"search":{"allow_expensive_queries":"true"}}}'

    support = SimpleNamespace(subprocess=SimpleNamespace(Popen=lambda *a, **kw: started.append(a)), bounded_request=request)
    monkeypatch.setattr(base, "load_support", lambda: support)
    before = base.load_support, base.artifact_hashes, base.check_index, base.emit_line, base.ObservedSearch

    def execute():
        value = deepcopy(baseline)
        value["artifactHashes"] = base.artifact_hashes()
        assert len(value["artifactHashes"]) == len(baseline["artifactHashes"]) + 4
        base.emit_line(BytesIO(), value)
        loaded = base.load_support()
        loaded.subprocess.Popen(["java", runner.MAIN_CLASS, "--server.port=19201"], cwd=tmp_path / "es-query-service")
        for _ in range(2): base.check_index(loaded, {})
        base.emit_line(BytesIO(), {"event": "terminal", "status": "measured"})
        if fault: raise RuntimeError("synthetic")
        return 0

    monkeypatch.setattr(runner.benchmark, "main", execute)
    if fault:
        with pytest.raises(RuntimeError, match="synthetic"): runner.main()
    else: assert runner.main() == 0
    assert before == (base.load_support, base.artifact_hashes, base.check_index, base.emit_line, base.ObservedSearch)
    assert emitted[0]["baselineSha256"] == runner.BASELINE_SHA
    assert emitted[0]["profileOverride"] == runner.FLAG
    assert emitted[-1]["clusterSettingReads"] == 2 and emitted[-1]["profileFlagLaunches"] == 1
    assert reads == ["GET", "index", "GET", "index"] and len(started) == 1
    assert original[4] is base.ObservedSearch


@pytest.mark.asyncio
async def test_observation_adds_only_elapsed_time(monkeypatch):
    base = runner.base
    monkeypatch.setattr(runner, "load_baseline", lambda: {})
    captured = []

    def execute():
        captured.append(base.ObservedSearch)
        return 0

    monkeypatch.setattr(runner.benchmark, "main", execute)
    runner.main()

    class Delegate:
        async def search(self, **kwargs):
            return SimpleNamespace(candidates=(), logical_domain_id="tax.policy", path=SimpleNamespace(value="keyword"),
                                   kind=SimpleNamespace(value="no_result"))

    rows = []
    value = await captured[0](Delegate(), {}, rows).search()
    assert value.kind.value == "no_result"
    assert set(rows[0]) == {"stage", "domain", "path", "status", "candidates", "durationMs"}
    assert rows[0]["durationMs"] >= 0


def test_missing_launch_is_failed_terminal_not_lost_evidence(monkeypatch):
    terminal = {"event": "terminal", "status": "measured"}
    emitted = []
    monkeypatch.setattr(runner.base, "emit_line", lambda stream, value: emitted.append(dict(value)))

    def execute():
        runner.base.emit_line(BytesIO(), terminal)
        return 0 if terminal["status"] == "measured" else 1

    monkeypatch.setattr(runner.benchmark, "main", execute)
    assert runner.main() == 1
    assert emitted[0]["status"] == "failed" and emitted[0]["profileFlagLaunches"] == 0
    assert emitted[0]["failureReason"] == "probe_artifacts_changed"


def test_original_preflight_failure_and_source_revision_remain_verifiable():
    path = runner.BASELINE.with_name("document_number_benchmark.preflight-failure.v1.jsonl")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "7489e996950a79d4c10cda8f886c86332b1280b535ccce29b791e88c3b159f85"
    prepared, terminal = (json.loads(line) for line in raw.splitlines())
    assert prepared["head"] == "8ec1160dc72985370efd24b253dd3da25f76cd8a"
    source = subprocess.check_output(["git", "show", prepared["head"] +
        ":agent-runtime/tests/system_e2e/knowledge_document_number_benchmark_v1.py"], cwd=runner.base.REPO)
    assert hashlib.sha256(source).hexdigest() == prepared["comparisonSha256"]
    assert terminal["status"] == "failed" and terminal["clusterSettingReads"] == 1
    assert terminal["counts"] == {"search": 0, "embedding": 0, "rerank": 0}
    assert all(terminal[k] == 0 for k in ("modelCalls", "businessCalls", "indexWrites", "profileFlagLaunches", "retry", "resume"))
