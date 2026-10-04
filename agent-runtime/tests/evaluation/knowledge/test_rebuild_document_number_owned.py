"""Synthetic ownership/failure checks; no real process, port, HTTP or secrets."""
import asyncio
import base64
from dataclasses import asdict, replace
from hashlib import sha256
import json
import socket
import subprocess

import pytest

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_owned as o
from tests.evaluation.knowledge import rebuild_document_number_projection as x
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding
from tests.evaluation.knowledge.test_rebuild_document_number_projection import proof

PORTS = (18221, 18222, 19321, 19322)
BINDING = o.ReadBinding("synthetic-read", "synthetic-index", "synthetic-uuid", "synthetic-v1")
SECRET = b"\xfb\xff\xff" * 16  # Standard Base64 contains both '+' and '/'.


@pytest.fixture(autouse=True)
def no_real_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real resource acquisition attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(o.subprocess, "Popen", forbidden)
    monkeypatch.setattr(o.httpx.Client, "send", forbidden)
    monkeypatch.setattr(o.httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(o.shared, "_port_guard", lambda ports: None)


@pytest.fixture
def pair(tmp_path):
    draft = p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))
    jars, configs, proofs = [], [], []
    for arm in p.ARMS:
        build = tmp_path / arm
        jar = build / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
        jar.parent.mkdir(parents=True)
        jar.write_bytes(arm.encode())
        config = build / "config-service/src/main/resources/config"
        config.mkdir(parents=True)
        jars.append(jar)
        configs.append(config)
        proofs.append(replace(proof(draft, arm), jar_sha256=sha256(jar.read_bytes()).hexdigest()))
    return x.ProjectedJavaPair(draft, tmp_path / "fake-java", tuple(jars), tuple(configs), tuple(proofs), {})


@pytest.fixture
def journal(tmp_path):
    binding = JournalBinding("synthetic-document-number-001", "f" * 40, "1" * 64, "2" * 64,
                             "3" * 64, "4" * 64, "synthetic_non_live")
    with AttemptJournal(directory=tmp_path / binding.run_id, binding=binding,
                        limits=(("javaHealth", 2),)) as value:
        yield value


class Proxy:
    def __init__(self, port, *, fail=False):
        self.port, self.closed, self.fail = port, False, fail
    def close(self):
        if self.fail:
            raise RuntimeError("synthetic-private")
        self.closed = True


class Process:
    def __init__(self, pid):
        self.pid, self.result, self.actions = pid, None, []
    def poll(self):
        return self.result
    def terminate(self):
        self.actions.append("terminate")
    def wait(self, timeout):
        self.actions.append(("wait", timeout))
        self.result = 0
    def kill(self):
        self.actions.append("kill")


class AsyncClient:
    def __init__(self, *, fail=False):
        self.is_closed, self.fail = False, fail
    async def aclose(self):
        if self.fail:
            raise asyncio.CancelledError
        self.is_closed = True


class Backend:
    def __init__(self):
        self.is_closed = False
    def close(self):
        self.is_closed = True


def configure(monkeypatch, pair):
    monkeypatch.setattr(o.shared, "_frozen_runtime_config_dir",
        lambda jar, head: (pair.configs[pair.jars.index(jar)].resolve(), ()))


def resources(pair, journal):
    value = o.OwnedJavaResources(pair=pair, journal=journal, ports=PORTS)
    for port in PORTS[2:]:
        value.add_proxy(Proxy(port))
    return value


async def test_two_owned_handles_stop_clients_close_before_jar_lease_release(monkeypatch, pair, journal):
    configure(monkeypatch, pair)
    calls, guards = [], []
    monkeypatch.setattr(o.shared, "_port_guard", lambda ports: guards.append(ports))
    def popen(args, **kwargs):
        process = Process(100 + len(calls))
        calls.append((args, kwargs, process))
        return process
    monkeypatch.setattr(o.subprocess, "Popen", popen)
    monkeypatch.setattr(x.os, "environ", {"PATH": "safe", "LLM_API_KEY": "synthetic-private",
        "JAVA_TOOL_OPTIONS": "synthetic-private", "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": "synthetic-private"})
    value = resources(pair, journal)
    async_client, backend = AsyncClient(), Backend()
    monkeypatch.setattr(o, "build_knowledge_http_client", lambda url: async_client)
    monkeypatch.setattr(o.httpx, "Client", lambda **kwargs: backend)
    assert value.open_client(PORTS[0]) is async_client
    assert value.open_backend() is backend
    for arm in reversed(p.ARMS):  # Ownership need not depend on insertion order.
        value.start_java(arm, binding=BINDING, secret=SECRET)
    monkeypatch.setattr(o.shared, "_listener_owner", lambda port: value.processes[p.ARMS[PORTS.index(port)]].pid)
    value.require_listeners()
    assert pair.resources_released is False
    assert len(calls) == 2
    for args, kwargs, process in calls:
        assert args[0] == str(pair.java) and "--es.query.knowledge.b-isolation-fixed-target=false" in args
        assert "knowledge-b-isolation" not in " ".join(args)
        assert "synthetic-private" not in repr((args, kwargs))
        encoded = kwargs["env"]["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"]
        assert "+" in encoded and "/" in encoded and base64.b64decode(encoded, validate=True) == SECRET
        assert kwargs["env"] == {"PATH": "safe", "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": encoded}
        assert all(kwargs[key] == subprocess.DEVNULL for key in ("stdin", "stdout", "stderr"))
        assert kwargs["shell"] is False
    report = await value.close()
    assert all(asdict(report).values()) and pair.resources_released
    assert async_client.is_closed and backend.is_closed and all(proxy.closed for proxy in value.proxies)
    assert all(process.poll() == 0 and process.actions == ["terminate", ("wait", 20)]
               for process in value.processes.values())
    assert guards == [PORTS, PORTS]
    log = json.loads(journal._path.read_bytes().splitlines()[-1])
    assert log["cleanupVerifiedByJournal"] is False and log["qualityAssessment"] == "Not assessed"
    with pytest.raises(p.ProtocolError, match="resources_closed"):
        await value.close()


async def test_partial_startup_failure_cleans_the_registered_first_process(monkeypatch, pair, journal):
    configure(monkeypatch, pair)
    process = Process(101)
    calls = []
    def popen(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise OSError("synthetic-private")
        return process
    monkeypatch.setattr(o.subprocess, "Popen", popen)
    value = resources(pair, journal)
    with pytest.raises(p.ProtocolError, match="owned_start_failed") as caught:
        async with value:
            value.start_java("old", binding=BINDING, secret=SECRET)
            value.start_java("current", binding=BINDING, secret=SECRET)
    assert caught.value.__context__ is None
    assert process.poll() == 0 and pair.resources_released
    assert len(value.processes) == 1 and all(proxy.closed for proxy in value.proxies)


async def test_listener_pid_drift_never_kills_unknown_listener(monkeypatch, pair, journal):
    configure(monkeypatch, pair)
    monkeypatch.setattr(o.subprocess, "Popen", lambda *args, **kwargs: Process(101))
    value = resources(pair, journal)
    for arm in p.ARMS:
        value.start_java(arm, binding=BINDING, secret=SECRET)
    monkeypatch.setattr(o.shared, "_listener_owner", lambda port: 999)
    with pytest.raises(p.ProtocolError, match="listener_changed"):
        value.require_listeners()
    # Occupied port after stopping our handles is a cleanup failure, not
    # permission to stop PID999 or to remove the attested JARs.
    monkeypatch.setattr(o.shared, "_port_guard", lambda ports: p.require(False, "occupied"))
    with pytest.raises(p.ProtocolError, match="cleanup_failed"):
        await value.close()
    assert all(process.poll() == 0 for process in value.processes.values())
    assert pair.resources_released is False and all(jar.exists() for jar in pair.jars)


@pytest.mark.parametrize("failure", ["process", "proxy", "client", "port"])
async def test_each_cleanup_failure_is_recorded_and_retains_jar_lease(monkeypatch, pair, journal, failure):
    value = resources(pair, journal)
    client = AsyncClient(fail=failure == "client")
    value.clients.append(client)
    if failure == "process":
        monkeypatch.setattr(o.shared, "_stop_owned", lambda processes: False)
    if failure == "proxy":
        value.proxies[0].fail = True
    if failure == "port":
        monkeypatch.setattr(o.shared, "_port_guard", lambda ports: p.require(False, "occupied"))
    with pytest.raises(p.ProtocolError, match="owned_cleanup_failed") as caught:
        async with value:
            raise RuntimeError("synthetic-private")
    assert caught.value.__suppress_context__ is True
    assert pair.resources_released is False and value.closed
    log = json.loads(journal._path.read_bytes().splitlines()[-1])
    assert log["reason"] == "cleanup_failed" and log["releaseAllowed"] is False
    assert not all(log["reportedCleanup"].values())


async def test_evidence_failure_cannot_prevent_resource_cleanup(monkeypatch, pair, journal):
    value = resources(pair, journal)
    client = AsyncClient()
    value.clients.append(client)
    monkeypatch.setattr(journal, "_append", lambda data: p.require(False, "synthetic-write-failed"))
    with pytest.raises(p.ProtocolError, match="owned_cleanup_failed"):
        await value.close()
    assert client.is_closed and all(proxy.closed for proxy in value.proxies)
    assert pair.resources_released is True


async def test_body_cancellation_still_runs_owned_cleanup(pair, journal):
    value = resources(pair, journal)
    with pytest.raises(asyncio.CancelledError):
        async with value:
            raise asyncio.CancelledError
    assert pair.resources_released and value.closed


@pytest.mark.parametrize("failure", ["jar", "config", "proxy", "secret"])
async def test_bad_start_binding_fails_before_any_process(monkeypatch, pair, journal, failure):
    configure(monkeypatch, pair)
    value = resources(pair, journal)
    if failure == "jar":
        pair.jars[0].write_bytes(b"changed")
    if failure == "config":
        monkeypatch.setattr(o.shared, "_frozen_runtime_config_dir", lambda *args: (pair.configs[1], ()))
    if failure == "proxy":
        value.proxies[0].closed = True
    with pytest.raises(p.ProtocolError):
        value.start_java("old", binding=BINDING, secret=base64.urlsafe_b64encode(SECRET).decode() if failure == "secret" else SECRET)
    assert not value.processes
    await value.close()


@pytest.mark.parametrize("field", ["read_alias", "index_name", "index_uuid", "mapping_version"])
def test_binding_rejects_paths_controls_and_non_strings(field):
    for invalid in ("../index", "a\nb", "a/b", "", True):
        with pytest.raises(p.ProtocolError, match="binding_invalid"):
            replace(BINDING, **{field: invalid})
