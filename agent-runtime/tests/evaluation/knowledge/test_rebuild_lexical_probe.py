"""Fake-only exact lexical probe tests; never use ES, Java or credentials."""
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_lexical_probe as p


@pytest.fixture
def spec():
    fixture = p.decode((p.ROOT / p.FIXTURE).read_bytes())
    previous = p.decode((p.ROOT / p.SOURCE).read_bytes())
    binding = previous["indexBindings"]["tax.policy"]
    return {"cases": [next(item for item in fixture["cases"] if item["caseId"] == case_id)
                      for case_id in p.CASE_IDS],
            "binding": {**binding, "policySnapshot": binding["snapshotId"]}, "aliasFlags": {},
            "frozenHead": "a" * 40, "authorization": "test-only",
            "forbidden": {key: 0 for key in ("model", "embedding", "rerank", "writes", "retry", "resume")}}


@pytest.mark.parametrize("raw", [b"", b"[]", b"null", b'{"a":1,"a":2}', b'{"a":NaN}',
                                 b'{"a":Infinity}', b'{}{}', b'\xff', b" " * (p._MAX + 1)],
                         ids=["empty", "array", "null", "duplicate", "nan", "infinity", "trailing", "utf8", "size"])
def test_exact_json_rejects(raw):
    with pytest.raises(p.ProbeError):
        p.decode(raw)


def test_pretty_json_and_canonical_are_accepted():
    assert p.decode(b'{\n "a": 1\n}') == {"a": 1}
    assert p.decode(p.canonical({"a": "税务"})) == {"a": "税务"}


@pytest.mark.parametrize("kind,limit", p.LIMITS.items())
def test_send_before_budget_and_append_only(tmp_path, kind, limit):
    ledger = p.Ledger(tmp_path)
    for _ in range(limit):
        ledger.reserve(kind, "synthetic-public")
    with pytest.raises(p.ProbeError, match="budget_exceeded"):
        ledger.reserve(kind, "too-many")
    ledger.close()
    assert ledger.counts[kind] == limit
    assert len((tmp_path / "journal.jsonl").read_bytes().splitlines()) == limit
    with pytest.raises(FileExistsError):
        p.Ledger(tmp_path)


def test_environment_never_reads_or_inherits_keys(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "synthetic-secret")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "synthetic-injection")
    monkeypatch.setenv("JWT", "synthetic-token")
    assert not {"LLM_API_KEY", "JWT", "JAVA_TOOL_OPTIONS"} & p.safe_env().keys()


def test_write_once_cannot_overwrite(tmp_path):
    path = tmp_path / "finite.json"
    p.write_once(path, {"a": 1})
    with pytest.raises(FileExistsError):
        p.write_once(path, {"a": 2})
    assert p.decode(path.read_bytes()) == {"a": 1}


def backend(handler=lambda request: httpx.Response(200, headers={"Content-Type": "application/json"}, json={})):
    return httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                        transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/_cluster/health", b""), ("GET", "/other/_mapping", b""),
    ("GET", "/__counts", b""), ("PUT", "/_aliases", b"{}"),
    ("DELETE", "/index", b""), ("POST", "/other/_search", b"{}")])
def test_proxy_exact_routes_no_outbound(spec, tmp_path, method, path, body):
    ledger = p.Ledger(tmp_path)
    calls = []
    with backend(lambda request: calls.append(request) or httpx.Response(200, json={})) as es:
        proxy = p.ProbeProxy(spec, "old", 12345, ledger, es)
        with pytest.raises(p.ProbeError):
            proxy.forward(method, path, body)
    ledger.close()
    assert not calls and not ledger.events


def test_metadata_per_arm_two_profiles_only(spec, tmp_path):
    ledger = p.Ledger(tmp_path)
    with backend() as es:
        proxy = p.ProbeProxy(spec, "old", 12345, ledger, es)
        path = p.metadata_paths(spec)[0]
        proxy.forward("GET", path, b"")
        proxy.forward("GET", path, b"")
        with pytest.raises(p.ProbeError, match="repeated"):
            proxy.forward("GET", path, b"")
    ledger.close()
    assert ledger.counts["metadata"] == 2


@pytest.mark.parametrize("arm", ["old", "current"])
def test_physical_exact_four_original_questions_and_no_retry(spec, tmp_path, arm):
    ledger = p.Ledger(tmp_path)
    calls = []
    with backend(lambda request: calls.append(request) or httpx.Response(200, json={})) as es:
        proxy = p.ProbeProxy(spec, arm, 12345, ledger, es)
        for ordinal in range(4):
            proxy.expect(ordinal)
            query = p.canonical(p.expected_physical(spec["cases"][ordinal]["question"], arm, ordinal))
            proxy.forward("POST", f'/{spec["binding"]["readAlias"]}/_search', query)
            with pytest.raises(p.ProbeError, match="search_not_expected"):
                proxy.forward("POST", f'/{spec["binding"]["readAlias"]}/_search', query)
    ledger.close()
    assert proxy.completed == 4 and len(calls) == 4


@pytest.mark.parametrize("change", ["knn", "size", "query", "gold", "source", "filter", "duplicate-json"])
def test_query_mutation_denied_before_es(spec, tmp_path, change):
    ledger = p.Ledger(tmp_path)
    calls = []
    with backend(lambda request: calls.append(request) or httpx.Response(200, json={})) as es:
        proxy = p.ProbeProxy(spec, "current", 12345, ledger, es)
        proxy.expect(0)
        body = p.expected_physical(spec["cases"][0]["question"], "current", 0)
        if change == "knn":
            body["knn"] = {}
        elif change == "size":
            body["size"] = 100
        elif change == "query":
            body["query"] = {"match_all": {}}
        elif change == "gold":
            body["gold"] = "lodging"
        elif change == "source":
            body["_source"] = True
        elif change == "filter":
            body["query"]["bool"]["filter"] = []
        raw = p.canonical(body)
        if change == "duplicate-json":
            raw = b'{"size":21,' + raw[1:]
        with pytest.raises(p.ProbeError):
            proxy.forward("POST", f'/{spec["binding"]["readAlias"]}/_search', raw)
    ledger.close()
    assert not calls and ledger.counts["search"] == 0


def test_helpers_differ_only_joint_issuer_signal(spec):
    values = [(p.expected_physical(item["question"], "old", i),
               p.expected_physical(item["question"], "current", i)) for i, item in enumerate(spec["cases"])]
    assert [old == current for old, current in values] == [True, True, False, True]
    for i in range(4):
        request = p.typed_request(spec, i)
        assert request.query_text == spec["cases"][i]["question"]
        assert request.query_vector is None and request.candidate_limit == 20


@pytest.mark.parametrize("fault", ["encoding", "media", "product", "size"])
def test_bounded_response(spec, fault):
    headers = {"Content-Type": "application/json"}
    body = b"{}"
    if fault == "encoding":
        headers["Content-Encoding"] = "gzip"
    elif fault == "media":
        headers["Content-Type"] = "text/plain"
    elif fault == "product":
        headers["X-Elastic-Product"] = "not-es"
    else:
        body = b"x" * (p._MAX + 1)
    with backend(lambda request: httpx.Response(200, headers=headers, stream=httpx.ByteStream(body))) as es:
        with pytest.raises(p.ProbeError):
            p.bounded(es, "GET", "/synthetic")


@pytest.mark.parametrize("fault", [None, "alias", "uuid", "mapping", "http"])
def test_pre_post_metadata_not_full_snapshot(spec, tmp_path, fault):
    name, alias = spec["binding"]["indexName"], spec["binding"]["readAlias"]
    mapping = {"_meta": {"mapping_version": spec["binding"]["mappingVersion"]}, "properties": {}}
    spec["binding"]["mappingSha256"] = sha256(p.canonical(mapping) + b"\n").hexdigest()
    responses = [
        {name: {"aliases": {alias: {"filter": {}} if fault == "alias" else {}}}},
        {name: {"settings": {"index": {"uuid": "changed" if fault == "uuid" else spec["binding"]["indexUuid"]}}}},
        {name: {"mappings": {**mapping, **({"extra": 1} if fault == "mapping" else {})}}},
    ]
    ledger = p.Ledger(tmp_path)
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(503 if fault == "http" else 200, json=responses[len(calls) - 1])
    with backend(respond) as es:
        if fault is None:
            assert p.attest_metadata(es, ledger, spec, "pre")["fullRecordFingerprint"] == "not_observed"
        else:
            with pytest.raises(p.ProbeError):
                p.attest_metadata(es, ledger, spec, "pre")
    ledger.close()
    assert len(calls) <= 3 and ledger.counts["metadata"] == len(calls)


@pytest.mark.parametrize("name,mode", [("../../outside", 0), ("/absolute", 0), ("link", 0o120777)])
def test_archive_traversal_and_symlink_rejected(tmp_path, name, mode):
    raw = BytesIO()
    with ZipFile(raw, "w") as archive:
        info = ZipInfo(name)
        info.external_attr = mode << 16
        archive.writestr(info, "synthetic")
    with pytest.raises(p.ProbeError):
        p.extract_archive(raw.getvalue(), tmp_path)


def test_java_normal_alias_no_fixed_target_no_cluster_health(spec, tmp_path):
    args = p.java_args(spec, tmp_path / "jar", tmp_path, 0, "java-test")
    assert "--es.query.knowledge.b-isolation-fixed-target=false" in args
    assert not any("b-isolation-run-id" in value for value in args)
    assert "--management.endpoint.health.group.knowledge-validation.include=readinessState" in args
    assert all("LLM_API_KEY" not in value for value in args)


def test_readiness_total_budget_no_jwt(monkeypatch, tmp_path):
    ledger = p.Ledger(tmp_path)
    process = SimpleNamespace(poll=lambda: None, pid=321)
    monkeypatch.setattr(p.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(p, "bounded", lambda *args, **kwargs: (503, "application/json", b"{}", None))
    for _ in range(2):
        with pytest.raises(p.ProbeError, match="readiness_exhausted"):
            p.ready(process, 12345, ledger)
    with pytest.raises(p.ProbeError, match="budget_exceeded"):
        p.ready(process, 12345, ledger)
    ledger.close()
    assert ledger.counts["health"] == 40


def test_build_failure_sealed_and_cleanup_owned_only(monkeypatch, tmp_path, spec):
    monkeypatch.setattr(p.shared, "_require_locked_python_environment", lambda mode: None)
    monkeypatch.setattr(p.shared, "_java_runtime_executable", lambda: "synthetic-java")
    monkeypatch.setattr(p.shared, "_port_guard", lambda ports: None)
    stopped = []
    monkeypatch.setattr(p.shared, "_stop_owned", lambda processes: stopped.append(list(processes)) or True)
    @contextmanager
    def failed_build(*args):
        raise p.ProbeError("build_failed")
        yield
    monkeypatch.setattr(p, "artifacts", failed_build)
    result = p.run(spec, tmp_path)
    assert result["status"] == "failed_unconsumed" and result["reason"] == "build_failed"
    assert stopped == [[]] and not (tmp_path / "consumed.json").exists()
    assert result["counts"] == dict.fromkeys(p.LIMITS, 0)
    assert p.decode((tmp_path / "result.json").read_bytes())["cleanup"] is True


@pytest.mark.parametrize("fault", [None, "startup", "typed", "postflight", "cleanup", "archive-exit", "late-violation"])
def test_same_runner_fake_terminal_and_cleanup_order(monkeypatch, tmp_path, spec, fault):
    """No real socket/process: exercise run's complete success/failure scopes."""
    fixture = p.decode((p.ROOT / p.FIXTURE).read_bytes())
    spec["sources"] = fixture["sources"]
    p.write_once(tmp_path / "manifest.json", spec)
    timeline = []
    monkeypatch.setattr(p.shared, "_require_locked_python_environment", lambda mode: None)
    monkeypatch.setattr(p.shared, "_java_runtime_executable", lambda: "synthetic-java")
    monkeypatch.setattr(p.shared, "_port_guard", lambda ports: None)
    monkeypatch.setattr(p, "prepare_spec", lambda head: spec)
    @contextmanager
    def build(*args):
        try:
            yield [(tmp_path / "old.jar", tmp_path), (tmp_path / "current.jar", tmp_path)]
        finally:
            assert "stop-java" in timeline and "close-proxy" in timeline
            timeline.append("remove-archive")
            if fault == "archive-exit":
                raise p.ProbeError("archive_cleanup_failed")
    monkeypatch.setattr(p, "artifacts", build)
    processes = []
    def launch(*args, **kwargs):
        process = SimpleNamespace(pid=300 + len(processes), poll=lambda: None)
        processes.append(process)
        return process
    monkeypatch.setattr(p.subprocess, "Popen", launch)
    monkeypatch.setattr(p.shared, "_listener_owner", lambda port: processes[p.PORTS.index(port)].pid)
    monkeypatch.setattr(p.shared, "_stop_owned", lambda processes: timeline.append("stop-java") or True)
    def metadata(es, ledger, spec, phase):
        if fault == "postflight" and phase == "post":
            raise p.ProbeError("mapping_drift")
        for path in p.metadata_paths(spec):
            ledger.reserve("metadata", phase + path)
        return {"phase": phase, "fullRecordFingerprint": "not_observed"}
    monkeypatch.setattr(p, "attest_metadata", metadata)
    monkeypatch.setattr(p.ProbeProxy, "start", lambda self: None)
    def close(self):
        timeline.append("close-proxy")
        if fault == "cleanup":
            raise p.ProbeError("proxy_cleanup_failed")
        if fault == "late-violation":
            self.violations += 1
    monkeypatch.setattr(p.ProbeProxy, "close", close)
    proxies = []
    old_init = p.ProbeProxy.__init__
    def initialize(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        proxies.append(self)
    monkeypatch.setattr(p.ProbeProxy, "__init__", initialize)
    def ready(process, port, ledger):
        ledger.reserve("health", str(port))
        if fault == "startup":
            raise p.ProbeError("java_exited")
        for path in p.metadata_paths(spec):
            for _ in range(2):
                ledger.reserve("metadata", path)
    monkeypatch.setattr(p, "ready", ready)
    def respond(client, method, path, body=b"", headers=None, **kwargs):
        proxy = proxies[0 if client.base_url.port == p.PORTS[0] else 1]
        ordinal = proxy.expected
        assert ordinal is not None
        if fault == "typed":
            return 500, "application/json", b"{}", None
        proxy.expected = None
        proxy.completed += 1
        proxy.ledger.reserve("search", proxy.arm + spec["cases"][ordinal]["caseId"])
        return 200, "application/json", p.canonical({"schemaVersion": 1, "logicalDomainId": "tax.policy",
            "retrievalProfileId": "tax-policy-v1", "path": "keyword", "profileVersion": "tax-knowledge-search-v1",
            "indexSnapshotId": spec["binding"]["policySnapshot"], "readPolicyVersion": "tax-public-authenticated-v1",
            "truncated": False, "candidates": []}), None
    monkeypatch.setattr(p, "bounded", respond)
    result = p.run(spec, tmp_path)
    assert result["status"] == ("completed" if fault is None else "failed_consumed")
    assert result["cleanup"] is (fault != "cleanup")
    assert (tmp_path / "consumed.json").is_file()
    assert timeline.index("stop-java") < timeline.index("close-proxy") < timeline.index("remove-archive")
    if fault is None:
        assert result["counts"] == {"health": 2, "metadata": 18, "typed": 8, "search": 8}
        assert len(result["cases"]) == 8
    elif fault in ("startup", "typed"):
        assert result["counts"]["typed"] == (1 if fault == "typed" else 0)
        assert not result["cases"]
    assert result["forbiddenActual"] == {"model": 0, "embedding": 0, "rerank": 0, "writes": 0}


def test_actuator_vendor_media_exact_health_only(monkeypatch, tmp_path):
    ledger = p.Ledger(tmp_path)
    process = SimpleNamespace(poll=lambda: None, pid=321)
    monkeypatch.setattr(p.shared, "_listener_owner", lambda port: 321)
    client_type = httpx.Client
    def client(**kwargs):
        return client_type(**kwargs, transport=httpx.MockTransport(lambda request:
            httpx.Response(200, headers={"Content-Type": "application/vnd.spring-boot.actuator.v3+json"},
                           json={"status": "UP"})))
    monkeypatch.setattr(p.httpx, "Client", client)
    p.ready(process, 12345, ledger)
    with client(base_url="http://127.0.0.1:9200", trust_env=False) as es:
        with pytest.raises(p.ProbeError, match="media_invalid"):
            p.bounded(es, "GET", "/_mapping")
    ledger.close()
    assert ledger.counts["health"] == 1


@pytest.mark.parametrize("status,cleanup,exit_code", [("completed", True, 0),
    ("failed_consumed", True, 1), ("failed_unconsumed", True, 1), ("completed", False, 1)])
def test_cli_failure_is_nonzero(monkeypatch, tmp_path, spec, status, cleanup, exit_code):
    p.write_once(tmp_path / "manifest.json", spec)
    monkeypatch.setattr(p, "DIRECTORY", tmp_path)
    monkeypatch.setattr(p, "prepare_spec", lambda head: spec)
    monkeypatch.setattr(p.shared, "_git", lambda *args: "a" * 40)
    monkeypatch.setattr(p, "run", lambda *args: {"status": status, "cleanup": cleanup,
                                               "reason": None, "counts": {}})
    monkeypatch.setattr(sys, "argv", ["probe", "execute", "--manifest-sha256",
        sha256((tmp_path / "manifest.json").read_bytes()).hexdigest()])
    with pytest.raises(SystemExit) as raised:
        p.main()
    assert raised.value.code == exit_code


def test_proxy_half_packet_handler_is_closed_without_es(spec, tmp_path):
    """Loopback synthetic connection only; backend is entirely MockTransport."""
    ledger = p.Ledger(tmp_path)
    calls = []
    with backend(lambda request: calls.append(request) or httpx.Response(200, json={})) as es:
        proxy = p.ProbeProxy(spec, "old", 0, ledger, es)
        proxy.start()
        assert proxy.server is not None
        port = proxy.server.server_address[1]
        connection = socket.create_connection(("127.0.0.1", port), timeout=2)
        connection.sendall(b"POST /synthetic HTTP/1.0\r\nContent-Length: 100\r\n\r\nx")
        connection.shutdown(socket.SHUT_WR)
        connection.close()
        started = time.monotonic()
        proxy.close()
        assert time.monotonic() - started < 8
    ledger.close()
    assert not calls and not ledger.events


@pytest.mark.parametrize("fault", ["wrong-exit", "bad-json", "changed-body", "extra-line"])
def test_offline_actual_java_projection_fails_closed(monkeypatch, tmp_path, spec, fault):
    jar = tmp_path / "service.jar"
    jar.write_bytes(b"synthetic")
    monkeypatch.setattr(p, "extract_archive", lambda *args: None)
    java = tmp_path / "java.exe"
    java.touch()
    java.with_name("javac.exe").touch()
    monkeypatch.setattr(p.shared, "_java_runtime_executable", lambda: str(java))
    lines = [p.canonical(p.expected_physical(item["question"], "old", i))
             for i, item in enumerate(spec["cases"])]
    if fault == "bad-json":
        lines[0] = b"not-json"
    elif fault == "changed-body":
        lines[0] = b"{}"
    elif fault == "extra-line":
        lines.append(b"{}")
    monkeypatch.setattr(p.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=1 if fault == "wrong-exit" else 0, stdout=b"\n".join(lines)))
    with pytest.raises(p.ProbeError):
        p.java_projection(jar, spec, "old")


def test_proxy_thread_start_failure_closes_bound_port_without_shutdown(spec, tmp_path, monkeypatch):
    ledger = p.Ledger(tmp_path)
    with backend() as es:
        proxy = p.ProbeProxy(spec, "old", 0, ledger, es)
        def fail_start(self):
            raise RuntimeError("synthetic-start-failure")
        monkeypatch.setattr(p.Thread, "start", fail_start)
        with pytest.raises(RuntimeError):
            proxy.start()
        assert proxy.server is not None
        port = proxy.server.server_address[1]
        started = time.monotonic()
        proxy.close()
        assert time.monotonic() - started < 2
        with socket.socket() as check:
            check.bind(("127.0.0.1", port))
    ledger.close()
