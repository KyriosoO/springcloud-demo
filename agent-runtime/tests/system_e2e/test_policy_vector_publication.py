"""Publication/rollback failure paths use only fake transports and processes."""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest


@pytest.fixture
def runner():
    path = Path(__file__).parents[3] / "knowledge-corpus-tools/scripts/publish-policy-vector-v1.py"
    spec = importlib.util.spec_from_file_location("policy_publication_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bindings():
    return ({"expectedIndexName": "source", "expectedIndexUuid": "old", "readAlias": "read"},
            {"expectedIndexName": "candidate", "expectedIndexUuid": "new", "readAlias": "read"})


@pytest.mark.parametrize("fault", [None, "uuid", "unblocked", "numeric_block", "alias_drift", "target_alias",
                                    "lost_response", "numeric_ack", "smoke_failure", "foreign_on_rollback"])
def test_atomic_switch_and_exact_owner_rollback(runner, fault):
    _, support = runner.support_module()
    source, candidate = bindings()
    owner, writes = ["source"], []
    def handle(request):
        path = request.url.path
        if path.endswith("/_settings"):
            name = path.split("/")[1]
            value = {name: {"settings": {"index": {"uuid": "old" if name == "source" else "new",
                                                   "blocks": {"write": "true"}}}}}
            if fault == "uuid": value[name]["settings"]["index"]["uuid"] = "other"
            if fault == "unblocked": value[name]["settings"]["index"]["blocks"]["write"] = False
            if fault == "numeric_block": value[name]["settings"]["index"]["blocks"]["write"] = 1
        elif path == "/_alias/read":
            value = {"foreign" if fault == "alias_drift" else owner[0]: {"aliases": {"read": {}}}}
        elif path.endswith("/_alias"):
            name = path.split("/")[1]
            value = {name: {"aliases": {"foreign": {}} if fault == "target_alias" else {}}}
        else:
            assert path == "/_aliases" and request.method == "POST"
            value = json.loads(request.content)
            writes.append(value)
            remove, add = value["actions"]
            assert remove["remove"] == {"index": owner[0], "alias": "read", "must_exist": True}
            assert set(add["add"]) == {"index", "alias"}
            owner[0] = add["add"]["index"]
            if fault == "lost_response" and len(writes) == 1:
                raise httpx.ReadTimeout("private raw content")
            value = {"acknowledged": 1 if fault == "numeric_ack" and len(writes) == 1 else True, "errors": False}
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value).encode()), headers={"content-type": "application/json"})
    with httpx.Client(base_url="http://127.0.0.1:9200", transport=httpx.MockTransport(handle)) as client:
        publisher = runner.Publication(support, source, candidate, client)
        if fault in {"uuid", "unblocked", "numeric_block", "alias_drift", "target_alias"}:
            with pytest.raises(ValueError): publisher.move(source, candidate)
            assert not writes and not publisher.attempted
        else:
            if fault in {"lost_response", "numeric_ack"}:
                with pytest.raises((ValueError, httpx.ReadTimeout)): publisher.move(source, candidate)
            else:
                publisher.move(source, candidate)
            assert owner[0] == "candidate"
            if fault == "foreign_on_rollback":
                owner[0] = "foreign"
                with pytest.raises(ValueError, match="owner_changed"): publisher.restore_if_owned()
                assert len(writes) == 1 and owner[0] == "foreign"
            elif fault is not None:
                assert publisher.restore_if_owned() == "rolled_back"
                assert owner[0] == "source" and len(writes) == 2
                with pytest.raises(ValueError, match="write_budget"): publisher.request("POST", "/_aliases", {})
            else:
                assert len(writes) == 1


@pytest.mark.parametrize("failure", [None, "preflight", "smoke", "cleanup", "drift"])
def test_smoke_failure_stops_services_before_rollback(runner, monkeypatch, tmp_path, failure):
    rehearsal, support = runner.support_module()
    source, candidate = bindings()
    events = []
    def preflight(*args):
        if failure == "preflight": raise ValueError("preflight")
        return candidate, source, b"catalog", {"hash": "before"}
    monkeypatch.setattr(runner, "check_prerequisites", preflight)
    monkeypatch.setattr(runner, "verify_current_records", lambda *args: None)
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "0" * 40)
    monkeypatch.setattr(rehearsal, "artifact_hashes", lambda: {"hash": "after" if failure == "drift" else "before"})
    class Manager:
        attempted = False
        reads = writes = 0
        def __init__(self, *args): pass
        def move(self, *args):
            events.append("move")
            self.attempted = True
            self.writes = 1
        def restore_if_owned(self):
            assert events[-1] == "stop"
            events.append("rollback")
            self.writes = 2
            return "rolled_back"
        def guard(self, *args): pass
    monkeypatch.setattr(runner, "Publication", Manager)
    @contextmanager
    def services(binding, alias, result):
        events.append("start")
        try: yield {"private": "never record"}
        finally:
            events.append("stop")
            result.update(profileVerifierStartupPassed=True, ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)
            if failure == "cleanup": raise ValueError("cleanup")
    monkeypatch.setattr(support, "isolated_services", services)
    async def checks(binding, catalog, tokens, result):
        if failure == "smoke": raise ValueError("secret must not be output")
        result.update(typedCalls=16, embeddingCalls=2, checks=[{"status": "passed"}] * 16)
    monkeypatch.setattr(support, "typed_checks", checks)
    result = {}
    with (tmp_path / "result.jsonl").open("xb") as stream:
        if failure:
            with pytest.raises(ValueError): runner.publish(rehearsal, support, stream, result)
        else:
            runner.publish(rehearsal, support, stream, result)
    if failure == "preflight": assert events == []
    elif failure: assert events == ["move", "start", "stop", "rollback"] and result["rollback"] == "rolled_back"
    else: assert events == ["move", "start", "stop"] and result["status"] == "published"
    assert "never record" not in json.dumps(result)


def test_no_execution_without_flag_and_no_overwriting_result(runner, monkeypatch, tmp_path):
    output = tmp_path / "result.jsonl"
    monkeypatch.setattr(sys, "argv", ["publish", "--result", str(output)])
    with pytest.raises(SystemExit): runner.main()
    assert not output.exists()
    def fail(): raise ValueError("arbitrary private exception")
    monkeypatch.setattr(runner, "support_module", fail)
    monkeypatch.setattr(sys, "argv", ["publish", "--execute", "--result", str(output)])
    assert runner.main() == 1
    previous = output.read_bytes()
    assert json.loads(previous)["reason"] == "publication_failed_no_retry"
    assert b"arbitrary" not in previous
    with pytest.raises(FileExistsError): runner.main()
    assert previous == output.read_bytes()


@pytest.mark.parametrize("fault", [None, "records", "mapping", "settings", "uuid", "write_block", "end_drift"])
def test_both_full_record_fingerprints_and_definitions_are_rechecked(runner, monkeypatch, fault):
    _, support = runner.support_module()
    from knowledge_corpus_tools import vector_candidate as module
    source = json.loads((runner.REPO / "serviceCenter/knowledge-runtime-binding.v1.json").read_bytes())
    candidate = json.loads((runner.REPO / "serviceCenter/knowledge-runtime-binding.v2.json").read_bytes())
    names = [source["expectedIndexName"], candidate["expectedIndexName"]]
    seen, definition_calls = [], []
    base = {"aliases": {source["readAlias"]: {}}, "settings": {"index": {"uuid": source["expectedIndexUuid"],
            "blocks": {"write": "true"}, "number_of_shards": "1"}},
            "mappings": {"_meta": {"mapping_version": source["mappingVersion"]}, "properties": {"content": {"type": "text"}}}}
    class Build:
        def __init__(self, spec, client): self.spec = spec
        def source(self): return copy.deepcopy(base)
        def definition(self, name):
            definition_calls.append(name)
            value = copy.deepcopy(base)
            value["aliases"] = {}
            value["settings"]["index"]["uuid"] = candidate["expectedIndexUuid"]
            value["mappings"]["_meta"]["mapping_version"] = candidate["mappingVersion"]
            value["mappings"]["properties"].update({key: {"type": "keyword"} for key in module.TRACE_FIELDS})
            if fault == "mapping": value["mappings"]["properties"]["content"]["type"] = "keyword"
            if fault == "uuid": value["settings"]["index"]["uuid"] = "other"
            if fault == "write_block": value["settings"]["index"]["blocks"]["write"] = False
            if fault == "settings": value["settings"]["index"]["analysis"] = {}
            if fault == "end_drift" and len(definition_calls) > 1: value["aliases"] = {"other": {}}
            return value
        def scan(self, name):
            seen.append(name)
            assert name in names
            return name
    monkeypatch.setattr(module, "_Build", Build)
    fingerprints = ["fac81f8f0fc73b23b0b7719c846662faf35e20b7dc3a6a70379abad917e1e418",
                    "fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d"]
    monkeypatch.setattr(module, "_fingerprint", lambda value: "changed" if fault == "records" else fingerprints[names.index(value)])
    result = {}
    if fault:
        with pytest.raises(ValueError): runner.verify_current_records(support, source, candidate, result)
    else:
        runner.verify_current_records(support, source, candidate, result)
        assert seen == names and result["sourceFingerprint"] == fingerprints[0] and result["candidateFingerprint"] == fingerprints[1]
    if fault in {"mapping", "settings", "uuid", "write_block"}: assert not seen


@pytest.mark.parametrize("number,digest,status", [
    ("01", "6841870de283ce5fbd667c56c8258aa3996a5c8dad86d690973a16a301dab109", "failed"),
    ("02", "76b8456e510bb2228bfafbabf75f31251d982541719191ab5630b8ea554f227b", "passed"),
])
def test_immutable_rollback_evidence_is_not_quality_uat(runner, number, digest, status):
    path = runner.REPO / f"knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/rollback-rehearsal-20260908-{number}.jsonl"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    rows = [json.loads(line) for line in raw.splitlines()]
    total = rows[-1]
    assert total["status"] == status
    assert all(total[key] == 0 for key in ("modelCalls", "businessCalls", "onlineAliasWrites", "retry", "resume"))
    assert "not_quality_v3_e2e" in total["limitations"]
    if status == "passed":
        assert total["phasesPassed"] == 3 and total["typedCalls"] == 24 and total["embeddingCalls"] == 6
        assert len(rows) == 5
        assert all(row["status"] == "passed" and len(row["checks"]) == 8 for row in rows[1:4])
        assert all(row["ownedProcessesStopped"] and row["rawLogsDeleted"] and row["secretScanPassed"] for row in rows[1:4])


@pytest.mark.parametrize("busy", [None, 8091, 8092, 9201])
def test_publication_requires_default_runtime_and_access_ports_idle(runner, monkeypatch, busy):
    rehearsal, support = runner.support_module()
    old = json.loads((runner.REPO / "serviceCenter/knowledge-runtime-binding.v1.json").read_bytes())
    new = json.loads((runner.REPO / "serviceCenter/knowledge-runtime-binding.v2.json").read_bytes())
    monkeypatch.setattr(support, "preflight", lambda: (new, old, b"catalog"))
    proof = (runner.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/rollback-rehearsal-20260908-02.jsonl").read_bytes()
    monkeypatch.setattr(rehearsal, "artifact_hashes", lambda: json.loads(proof.splitlines()[0])["artifactHashes"])
    observed = []
    class Socket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def bind(self, address):
            observed.append(address[1])
            if address[1] == busy: raise OSError("port busy")
    monkeypatch.setattr(runner.socket, "socket", Socket)
    if busy:
        with pytest.raises(OSError): runner.check_prerequisites(rehearsal, support)
    else:
        runner.check_prerequisites(rehearsal, support)
        assert observed == [8090, 8091, 8092, 9201]


def test_published_result_remains_bound_to_actual_frozen_source(runner):
    path = runner.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/publication-20260908-01.jsonl"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "e716addba9d02979bc5104a6a1df1ead83b84bd6a0a9968686351e644b1917d0"
    rows = [json.loads(line) for line in raw.splitlines()]
    prepared, terminal = rows[0], rows[-1]
    frozen = runner.subprocess.check_output(["git", "show", prepared["head"] + ":knowledge-corpus-tools/scripts/publish-policy-vector-v1.py"], cwd=runner.REPO)
    assert hashlib.sha256(frozen).hexdigest() == prepared["launcherSha256"]
    assert terminal["status"] == "published" and terminal["onlineAliasWrites"] == 1
    assert terminal["typedCalls"] == 16 and terminal["embeddingCalls"] == 2 and len(terminal["checks"]) == 16
    assert terminal["integrityReadHttp"] == 130 and terminal["esManagementReads"] == 10
    assert all(terminal[key] == 0 for key in ("modelCalls", "businessCalls", "retry", "resume"))
    assert all(terminal[key] is True for key in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    assert "not_stage_b_uat" in terminal["limitations"]
