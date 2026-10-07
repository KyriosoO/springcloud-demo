"""Owned runtime assembly with in-memory HTTP and process/port seams only."""
import asyncio
from dataclasses import asdict
from hashlib import sha256
import json
import socket
import subprocess
import traceback

import httpx
import pytest

from agent_runtime.capability_api.contracts import CancellationSource
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_owned as o
from tests.evaluation.knowledge import rebuild_document_number_proxy as proxy_module
from tests.evaluation.knowledge import rebuild_document_number_runtime as r
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding
from tests.evaluation.knowledge.test_rebuild_document_number_owned import pair, Process, configure, PORTS, BINDING
from tests.evaluation.knowledge.test_rebuild_document_number_proxy import metadata
from tests.evaluation.knowledge.test_rebuild_document_number_stage import Scripted
from tests.helpers import ManualCancellationSignal


@pytest.fixture(autouse=True)
def no_real_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real operation attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(proxy_module.ThreadingHTTPServer, "__init__", forbidden)
    monkeypatch.setattr(o.shared, "_port_guard", lambda ports: None)


@pytest.fixture
def journal(tmp_path):
    binding = JournalBinding("synthetic-document-number-004", "f" * 40, "1" * 64, "2" * 64,
                             "3" * 64, "4" * 64, "synthetic_non_live")
    with AttemptJournal(directory=tmp_path / binding.run_id, binding=binding,
        limits=(("metadata", 18), ("javaHealth", 2), ("prewarmRerank", 1),
            ("typedSearch", 44), ("physicalSearch", 44), ("queryEmbedding", 10), ("rerank", 22))) as value:
        yield value


def wire(monkeypatch, pair, journal, *, failure=None):
    configure(monkeypatch, pair)
    proxies, processes, clients, actual, backend_calls = [], [], [], [], []
    paths, raw_metadata = proxy_module.metadata_paths(BINDING), metadata()
    hashes = tuple((path, sha256(raw).hexdigest()) for path, raw in zip(paths, raw_metadata, strict=True))
    def backend_reply(request):
        backend_calls.append(request)
        return httpx.Response(200, headers={"content-type": "application/json", "x-elastic-product": "Elasticsearch"},
            stream=httpx.ByteStream(dict(zip(paths, raw_metadata)).get(request.url.path, p.canonical({"hits": {"hits": []}}))))
    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                           transport=httpx.MockTransport(backend_reply))
    monkeypatch.setattr(o.OwnedJavaResources, "open_backend", lambda self: self.backends.append(backend) or backend)
    def proxy_start(self):
        proxies.append(self)
        if failure == "proxy_start" and len(proxies) == 2:
            raise RuntimeError("synthetic-private-provider")
    monkeypatch.setattr(proxy_module.DocumentNumberProxy, "start", proxy_start)
    def popen(args, **kwargs):
        arm = p.ARMS[len(processes)]
        if failure == "java_start" and arm == "current":
            raise OSError("synthetic-private-provider")
        process = Process(101 + len(processes))
        processes.append(process)
        if failure != "metadata_missing":
            for _ in range(2):
                for path in paths:
                    proxies[p.ARMS.index(arm)].forward("GET", path, b"")
        return process
    monkeypatch.setattr(o.subprocess, "Popen", popen)
    def listener(port):
        if failure == "listener_missing":
            raise o.shared.BLocalRunError("listener_owner_mismatch")
        if failure == "listener_unavailable":
            raise o.shared.BLocalRunError("listener_owner_unavailable")
        if failure == "listener_changed":
            return 999
        return processes[PORTS.index(port)].pid
    monkeypatch.setattr(o.shared, "_listener_owner", listener)
    class Bridge:
        def __init__(self, proxy): self.proxy, self.arm, self.gate = proxy, proxy.arm, self
        @property
        def case(self): return self.proxy.draft.cases[self.proxy.completed_cases]
        def forward(self, *, method, path, body, send): return self.proxy.forward(method, path, body)
    def open_client(self, port):
        async def respond(request):
            actual.append(request)
            if request.url.path == r._HEALTH:
                assert request.headers.get("authorization") is None
                if failure == "health_transport":
                    raise httpx.ReadError("synthetic-private-provider")
                content = b'{"status":"UP"}'
                if failure == "health_duplicate": content = b'{"status":"UP","status":"UP"}'
                elif failure == "health_down": content = b'{"status":"DOWN"}'
                elif failure == "health_oversize": content = b"x" * 4097
                elif failure == "cancel_health":
                    raise asyncio.CancelledError
                return httpx.Response(503 if failure == "health_http" else 200,
                    headers={"content-type": "text/html" if failure == "health_media" else "application/json"},
                    stream=httpx.ByteStream(content))
            payload = json.loads(request.content)
            if request.url.path == "/rerank" and len(payload["documents"]) == 40:
                if failure == "warmup_transport": raise httpx.ReadError("synthetic-private-provider")
                content = p.canonical({"model": "other" if failure == "warmup_model" else "BAAI/bge-reranker-v2-m3",
                    "results": [{"index": i, "text": text, "score": 0.5} for i, text in enumerate(payload["documents"])]})
            else:
                scripted = Scripted(Bridge(proxies[PORTS.index(port)])) if port in PORTS[:2] else Scripted()
                result = await scripted.send(request=r.BoundedHttpRequest(method="POST", relative_path=request.url.path,
                    headers=tuple(request.headers.items()), body=request.content, max_response_bytes=2 * 1024 * 1024), timeout_s=5)
                content = result.body
                if request.url.path == "/es/knowledge/search":
                    dto = json.loads(content)
                    dto["indexSnapshotId"] = ("a" * 64 if failure == "snapshot_drift"
                        else BINDING.profile_snapshot(payload["logicalDomainId"]))
                    if failure == "read_policy_drift": dto["readPolicyVersion"] = "other-policy"
                    content = p.canonical(dto)
                if failure == "pid_drift" and request.url.path == "/embed":
                    monkeypatch.setattr(o.shared, "_listener_owner", lambda port: 999)
                if failure == "client_drift" and request.url.path == "/embed":
                    clients[0].params = {"routing": "subset"}
            return httpx.Response(200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(content))
        client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False, follow_redirects=False,
                                  transport=httpx.MockTransport(respond))
        clients.append(client)
        self.clients.append(client)
        return client
    monkeypatch.setattr(o.OwnedJavaResources, "open_client", open_client)
    value = r.OwnedComparisonRuntime(pair=pair, journal=journal, binding=BINDING, ports=PORTS, metadata_sha256=hashes)
    return value, proxies, processes, clients, backend, actual, backend_calls


async def test_full_owned_assembly_retains_one_lease_and_counts_each_layer_once(monkeypatch, pair, journal):
    value, proxies, processes, clients, backend, actual, backend_calls = wire(monkeypatch, pair, journal)
    before = asyncio.all_tasks()
    result = await value.evaluate(cancellation=ManualCancellationSignal())
    assert asyncio.all_tasks() == before
    assert len(result.stage.cases) == 10 and len(result.stage.physical_witnesses) == 44
    assert journal.ledger.counts == {"metadata": 12, "javaHealth": 2, "prewarmRerank": 1,
                                   "typedSearch": 44, "physicalSearch": 44, "queryEmbedding": 10, "rerank": 22}
    assert len(backend_calls) == 56 and len(actual) == 79
    assert all(asdict(result.cleanup).values()) and pair.resources_released
    assert all(process.poll() == 0 for process in processes)
    assert all(client.is_closed for client in clients) and backend.is_closed
    assert all(proxy.closed and proxy.completed_cases == 10 for proxy in proxies)
    assert result.quality_assessment == "Not assessed" and not result.release_allowed
    finite = p.canonical(asdict(result)).decode() + journal._path.read_text(encoding="utf-8")
    tokens = [request.headers["authorization"] for request in actual if "authorization" in request.headers]
    assert tokens and len(set(tokens)) == 1 and all(token not in finite for token in tokens)
    assert pair.draft.cases[0].plan.original_question not in finite and "税务政策正文" not in finite
    assert journal.ledger.view()["pending"] == 0
    with pytest.raises(p.ProtocolError, match="already_attempted"):
        await value.evaluate(cancellation=ManualCancellationSignal())


@pytest.mark.parametrize("failure", ["proxy_start", "java_start", "listener_changed", "listener_missing",
    "listener_unavailable", "metadata_missing", "health_transport", "health_http", "health_duplicate",
    "health_down", "health_oversize", "health_media", "warmup_transport", "warmup_model", "pid_drift", "client_drift"])
async def test_startup_or_destination_failure_cleans_and_never_enters_later_cases(monkeypatch, pair, journal, failure):
    value, proxies, processes, clients, backend, actual, backend_calls = wire(monkeypatch, pair, journal, failure=failure)
    monkeypatch.setattr(r, "_STARTUP_SECONDS", 0.01)
    before = asyncio.all_tasks()
    with pytest.raises(p.ProtocolError, match="runtime_comparison_failed") as caught:
        await value.evaluate(cancellation=ManualCancellationSignal())
    assert asyncio.all_tasks() == before and journal.ledger.view()["pending"] == 0
    assert journal.ledger.view()["stopped"] and pair.resources_released
    assert backend.is_closed and all(client.is_closed for client in clients) and all(proxy.closed for proxy in proxies)
    assert all(process.poll() == 0 for process in processes)
    assert not any(request.url.path == "/es/knowledge/search" for request in actual)
    assert journal.ledger.counts["physicalSearch"] == journal.ledger.counts["rerank"] == 0
    assert journal.ledger.counts["queryEmbedding"] == (1 if failure in ("pid_drift", "client_drift") else 0)
    assert "synthetic-private-provider" not in "".join(traceback.format_exception(caught.value))
    with pytest.raises(p.ProtocolError, match="already_attempted"):
        await value.evaluate(cancellation=ManualCancellationSignal())


@pytest.mark.parametrize("where", ["before", "health", "cleanup"])
async def test_cancellation_drains_owned_cleanup_and_all_watcher_tasks(monkeypatch, pair, journal, where):
    value, proxies, processes, clients, backend, actual, _ = wire(monkeypatch, pair, journal,
        failure="cancel_health" if where == "health" else None)
    signal = ManualCancellationSignal()
    if where == "before": signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    if where == "cleanup":
        close = o.OwnedJavaResources.close
        entered, finish = asyncio.Event(), asyncio.Event()
        async def delayed_close(self):
            entered.set()
            await finish.wait()
            return await close(self)
        monkeypatch.setattr(o.OwnedJavaResources, "close", delayed_close)
        before = asyncio.all_tasks()
        task = asyncio.create_task(value.evaluate(cancellation=signal))
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        finish.set()
        with pytest.raises(asyncio.CancelledError): await task
    else:
        before = asyncio.all_tasks()
        with pytest.raises(asyncio.CancelledError): await value.evaluate(cancellation=signal)
    assert asyncio.all_tasks() == before and journal.ledger.view()["stopped"]
    assert journal.ledger.view()["pending"] == 0 and pair.resources_released
    if where != "before":
        assert backend.is_closed and all(client.is_closed for client in clients)
        assert all(proxy.closed for proxy in proxies) and all(process.poll() == 0 for process in processes)


@pytest.mark.parametrize("change", ["params", "cookie", "auth", "hook", "headers", "follow", "trust", "origin"])
async def test_client_mutation_prevents_counted_health_send(monkeypatch, pair, journal, change):
    value, _, _, clients, _, actual, _ = wire(monkeypatch, pair, journal)
    open_client = o.OwnedJavaResources.open_client
    def changed(self, port):
        client = open_client(self, port)
        if change == "params": client.params = {"routing": "subset"}
        elif change == "cookie": client.cookies.set("secret", "synthetic-private")
        elif change == "auth": client.auth = ("user", "synthetic-private")
        elif change == "hook": client.event_hooks["request"].append(lambda request: None)
        elif change == "headers": client.headers["Authorization"] = "synthetic-private"
        elif change == "follow": client.follow_redirects = True
        elif change == "trust": client._trust_env = True
        else: client.base_url = "http://127.0.0.1:1"
        return client
    monkeypatch.setattr(o.OwnedJavaResources, "open_client", changed)
    with pytest.raises(p.ProtocolError): await value.evaluate(cancellation=ManualCancellationSignal())
    assert not actual and journal.ledger.counts["javaHealth"] == 0 and all(client.is_closed for client in clients)


async def test_native_wait_is_bounded_observation_not_hidden_health_retry(monkeypatch, pair, journal):
    value, _, processes, _, _, actual, _ = wire(monkeypatch, pair, journal)
    observed = []
    def owner(port):
        observed.append(port)
        if len(observed) <= 2:
            raise o.shared.BLocalRunError("listener_owner_mismatch")
        return processes[PORTS.index(port)].pid
    monkeypatch.setattr(o.shared, "_listener_owner", owner)
    result = await value.evaluate(cancellation=ManualCancellationSignal())
    assert len(result.stage.cases) == 10 and len(observed) > 2
    assert [request.method for request in actual if request.url.path == r._HEALTH] == ["GET", "GET"]
    assert journal.ledger.counts["javaHealth"] == 2


async def test_signal_during_native_wait_sends_no_health_or_case_and_closes(monkeypatch, pair, journal):
    value, proxies, processes, clients, backend, actual, _ = wire(monkeypatch, pair, journal, failure="listener_missing")
    signal, observed = ManualCancellationSignal(), asyncio.Event()
    def owner(port):
        observed.set()
        raise o.shared.BLocalRunError("listener_owner_mismatch")
    monkeypatch.setattr(o.shared, "_listener_owner", owner)
    before = asyncio.all_tasks()
    task = asyncio.create_task(value.evaluate(cancellation=signal))
    await observed.wait()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    with pytest.raises(asyncio.CancelledError): await task
    assert asyncio.all_tasks() == before and not actual and not clients
    assert journal.ledger.counts["javaHealth"] == journal.ledger.counts["queryEmbedding"] == 0
    assert pair.resources_released and backend.is_closed and all(proxy.closed for proxy in proxies)
    assert all(process.poll() == 0 for process in processes)


async def test_health_provider_swallowing_work_cancel_cannot_send_peer_health_or_warmup(monkeypatch, pair, journal):
    value, proxies, processes, clients, backend, actual, _ = wire(monkeypatch, pair, journal)
    signal, swallowed = ManualCancellationSignal(), []
    open_client = o.OwnedJavaResources.open_client
    def wrapped_client(self, port):
        client = open_client(self, port)
        original = client._transport.handler
        async def respond(request):
            if not swallowed and request.url.path == r._HEALTH:
                actual.append(request)
                signal.cancel(CancellationSource.CLIENT_DISCONNECT)
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    swallowed.append(True)
                    return httpx.Response(200, headers={"content-type": "application/json"},
                        stream=httpx.ByteStream(b'{"status":"UP"}'))
            return await original(request)
        client._transport = httpx.MockTransport(respond)
        return client
    monkeypatch.setattr(o.OwnedJavaResources, "open_client", wrapped_client)
    before = asyncio.all_tasks()
    with pytest.raises(asyncio.CancelledError): await value.evaluate(cancellation=signal)
    assert asyncio.all_tasks() == before and swallowed == [True]
    assert [request.url.path for request in actual] == [r._HEALTH]
    assert journal.ledger.counts["javaHealth"] == 1 and journal.ledger.counts["prewarmRerank"] == 0
    assert journal.ledger.counts["queryEmbedding"] == journal.ledger.counts["typedSearch"] == 0
    assert journal.ledger.view()["pending"] == 0 and journal.ledger.events[-1].outcome == "cancelled"
    assert pair.resources_released and backend.is_closed and all(client.is_closed for client in clients)
    assert all(proxy.closed for proxy in proxies) and all(process.poll() == 0 for process in processes)


async def test_cleanup_failure_seals_finite_failure_and_cannot_return_stage_capture(monkeypatch, pair, journal):
    value, proxies, _, clients, backend, _, _ = wire(monkeypatch, pair, journal)
    monkeypatch.setattr(o.shared, "_stop_owned", lambda processes: False)
    with pytest.raises(p.ProtocolError, match="runtime_comparison_failed"):
        await value.evaluate(cancellation=ManualCancellationSignal())
    assert not pair.resources_released and journal.ledger.view()["pending"] == 0
    assert backend.is_closed and all(client.is_closed for client in clients) and all(proxy.closed for proxy in proxies)
    closed = json.loads(journal._path.read_bytes().splitlines()[-1])
    assert closed["reason"] == "cleanup_failed" and closed["reportedCleanup"]["processes_stopped"] is False
    assert closed["qualityAssessment"] == "Not assessed" and not closed["releaseAllowed"]


@pytest.mark.parametrize("swallow", [False, True])
async def test_startup_absolute_deadline_rejects_swallowed_cancellation_and_late_body(journal, swallow):
    actual = []
    async def respond(request):
        actual.append(request)
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            if not swallow: raise
            return httpx.Response(200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(b'{"status":"UP"}'))
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORTS[0]}", trust_env=False,
        transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(p.ProtocolError, match="startup_request_failed"):
            await r._exchange(client=client, journal=journal, kind="javaHealth", label="startup/old/health",
                method="GET", path=r._HEALTH, body=b"", maximum=4096, seconds=0.01, port=PORTS[0])
    assert len(actual) == journal.ledger.counts["javaHealth"] == 1
    assert journal.ledger.view()["pending"] == 0 and journal.ledger.view()["stopped"]


async def test_postflight_uses_same_live_ledger_before_cleanup_seal(monkeypatch, pair, journal):
    value, proxies, processes, clients, backend, _, _ = wire(monkeypatch, pair, journal)
    checks = []
    async def postcheck():
        assert not journal._closed and not journal.ledger.view()["stopped"]
        assert not pair.resources_released and not backend.is_closed
        assert all(process.poll() is None for process in processes)
        assert all(not client.is_closed for client in clients)
        for n in range(3):
            ticket = journal.ledger.begin("metadata", f"inventory/post/metadata/{n}", b"")
            journal.ledger.finish(ticket, "completed", 200)
        checks.append("postflight")
    value.postcheck = postcheck
    capture = await value.evaluate(cancellation=ManualCancellationSignal())
    assert checks == ["postflight"] and journal._closed and pair.resources_released
    assert dict(capture.counted_attempts)["metadata"] == 15
    assert dict(capture.stage.counted_attempts)["metadata"] == 12  # Stage-only boundary.
    assert all(proxy.closed for proxy in proxies) and backend.is_closed


async def test_failed_postflight_never_returns_success_capture(monkeypatch, pair, journal):
    value, proxies, processes, clients, backend, _, _ = wire(monkeypatch, pair, journal)
    async def postcheck():
        assert not journal._closed
        raise ValueError("synthetic-source-drift")
    value.postcheck = postcheck
    with pytest.raises(p.ProtocolError, match="runtime_comparison_failed"):
        await value.evaluate(cancellation=ManualCancellationSignal())
    assert journal._closed and journal.ledger.view()["stopped"] and pair.resources_released
    assert all(proxy.closed for proxy in proxies) and all(process.poll() == 0 for process in processes)
    assert backend.is_closed and all(client.is_closed for client in clients)


async def test_cancelled_postflight_receipt_drains_before_owned_cleanup(monkeypatch, pair, journal):
    value, proxies, processes, _, backend, _, _ = wire(monkeypatch, pair, journal)
    signal, entered, drained = ManualCancellationSignal(), asyncio.Event(), []
    async def postcheck():
        ticket = journal.ledger.begin("metadata", "inventory/post/metadata/0", b"")
        entered.set()
        try:
            await asyncio.Future()
        finally:
            assert not journal._closed and not backend.is_closed
            journal.ledger.finish(ticket, "cancelled")
            drained.append(True)
    value.postcheck = postcheck
    before = asyncio.all_tasks()
    task = asyncio.create_task(value.evaluate(cancellation=signal))
    await entered.wait()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    with pytest.raises(asyncio.CancelledError): await task
    assert drained == [True] and asyncio.all_tasks() == before
    assert journal._closed and journal.ledger.view()["pending"] == 0 and pair.resources_released
    assert all(proxy.closed for proxy in proxies) and all(process.poll() == 0 for process in processes)


async def test_startup_failure_cannot_enter_postflight(monkeypatch, pair, journal):
    value, _, _, _, _, _, _ = wire(monkeypatch, pair, journal, failure="proxy_start")
    async def postcheck():
        pytest.fail("postflight invoked after startup failure")
    value.postcheck = postcheck
    with pytest.raises(p.ProtocolError):
        await value.evaluate(cancellation=ManualCancellationSignal())


@pytest.mark.parametrize("failure", ["snapshot_drift", "read_policy_drift"])
async def test_joint_wrong_typed_binding_cannot_rerank_or_reach_peer_arm(monkeypatch, pair, journal, failure):
    value, _, _, _, _, actual, _ = wire(monkeypatch, pair, journal, failure=failure)
    with pytest.raises(p.ProtocolError, match="runtime_comparison_failed"):
        await value.evaluate(cancellation=ManualCancellationSignal())
    assert journal.ledger.counts["queryEmbedding"] == 1 and journal.ledger.counts["rerank"] == 0
    typed = [request for request in actual if request.url.path == "/es/knowledge/search"]
    assert typed and all(request.url.port == PORTS[0] for request in typed)
    assert journal.ledger.view()["stopped"] and journal.ledger.view()["pending"] == 0


@pytest.mark.parametrize("failure", [None, "no_pre", "post_drift", "no_post"])
async def test_model_identity_pre_and_post_are_bound_to_owned_runtime_before_seal(monkeypatch, pair, tmp_path, failure):
    # Reuse the real identity collector with a synthetic process provider;
    # no Docker, native HTTP, Java/server or inference operation is possible.
    from tests.evaluation.knowledge import rebuild_document_number_identity as identities
    from tests.evaluation.knowledge.test_rebuild_document_number_identity import model_fixture, Provider
    binding = JournalBinding("synthetic-document-number-009", "f" * 40, "1" * 64,
                             "2" * 64, "3" * 64, "4" * 64, "synthetic_non_live")
    monkeypatch.setattr(identities, "capture_static_identity", lambda *_: b'{"synthetic":true}\n')
    model, embedding, rerank = model_fixture(tmp_path, monkeypatch)
    preparation_ledger = identities.IdentityLedger(phases=("preparation",), checkpoint=lambda *_: None)
    expected = identities.IdentitySession(pair=pair, binding=BINDING, model=model, ledger=preparation_ledger,
        process=Provider(model, embedding, rerank), expected=None).capture("preparation")
    with AttemptJournal(directory=tmp_path / binding.run_id, binding=binding, identity_phases=("pre", "post"),
        limits=(("metadata", 18), ("javaHealth", 2), ("prewarmRerank", 1),
            ("typedSearch", 44), ("physicalSearch", 44), ("queryEmbedding", 10), ("rerank", 22))) as log:
        assert log.identity_ledger is not None
        provider = Provider(model, embedding, rerank, ledger=log.identity_ledger)
        identity = identities.IdentitySession(pair=pair, binding=BINDING, model=model,
            ledger=log.identity_ledger, process=provider, expected=expected)
        if failure != "no_pre": await identity.capture_async("pre")
        value, proxies, processes, clients, backend, actual, _ = wire(monkeypatch, pair, log)
        async def postcheck():
            assert not log._closed and not backend.is_closed and not pair.resources_released
            if failure == "post_drift": provider.rerank = {**rerank, "serviceSha256": "e" * 64}
            await identity.capture_async("post")
        if failure != "no_post": value.postcheck = postcheck
        if failure is None:
            capture = await value.evaluate(cancellation=ManualCancellationSignal())
            assert len(capture.stage.cases) == 10
        else:
            with pytest.raises(p.ProtocolError, match="runtime_comparison_failed"):
                await value.evaluate(cancellation=ManualCancellationSignal())
        assert log.identity_ledger.view()["pending"] == 0 and log.identity_ledger.view()["stopped"]
        if failure == "no_pre":
            assert processes == proxies == clients == actual == [] and provider.calls == []
            # Fake wire borrowed a backend before runtime, not an owned resource.
            backend.close()
        else:
            assert log._closed and pair.resources_released and backend.is_closed
            assert all(proxy.closed for proxy in proxies) and all(client.is_closed for client in clients)
            rows = [json.loads(line) for line in (tmp_path / binding.run_id / "attempts.jsonl").read_bytes().splitlines()]
            assert rows[-1]["nonHttpModelIdentityCounts"] == {"pre": 4, "post": 0 if failure == "no_post" else 4}
