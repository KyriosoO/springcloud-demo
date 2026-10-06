"""Synthetic confirmation, files and providers only; never a live run grant."""
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_document_number_runner as r
from tests.evaluation.knowledge import rebuild_document_number_runtime as runtime
from tests.evaluation.knowledge.rebuild_document_number_identity import IdentityCapture, ModelBinding
from tests.evaluation.knowledge.rebuild_document_number_inventory import InventoryCapture
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, CleanupReport
from tests.evaluation.knowledge.test_rebuild_document_number_owned import pair, PORTS, BINDING
from tests.evaluation.knowledge.test_rebuild_document_number_runtime import wire
from tests.helpers import ManualCancellationSignal
from agent_runtime.capability_api.contracts import CancellationSource

STATIC = b"synthetic-only-static-identity"


@pytest.fixture(autouse=True)
def no_real_operations(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real resource operation attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(r, "capture_static_identity", lambda *args: STATIC)
    monkeypatch.setattr(r.time, "time", lambda: 100)


@pytest.fixture
def scope(pair, tmp_path):
    model = ModelBinding("a" * 64, "b" * 64, "c" * 64, tmp_path / "fake-docker", "d" * 64,
                         "npipe:////./pipe/docker_engine")
    material = r.p.canonical({"synthetic": True})
    identity = IdentityCapture(sha256(STATIC).hexdigest(), "1" * 64, sha256(material).hexdigest(), material)
    inventory = b'{"records":[{"id":"synthetic-only"}]}\n'
    frozen = InventoryCapture(BINDING, "2" * 64, 3, "3" * 64, sha256(inventory).hexdigest(), (), inventory)
    return r.RunScope("synthetic-document-number-006", "P3_01:synthetic-only", "execution", "synthetic_non_live",
        90, 110, pair, BINDING, model, "2" * 64, sha256(STATIC).hexdigest(), 3, PORTS, frozen, identity)


def receipt(scope, raw):
    return r.ConfirmationReceipt(sha256(raw).hexdigest(), scope.reference, "e" * 64)


def setup(monkeypatch, scope, tmp_path, *, failure=None, actual_runtime=False):
    events, clients, logs = [], [], []
    original_journal = r.AttemptJournal
    def journal_factory(**kwargs):
        journal = original_journal(**kwargs)
        logs.append(journal)
        return journal
    monkeypatch.setattr(r, "AttemptJournal", journal_factory)
    def confirmed(raw):
        events.append("confirmed")
        return receipt(scope, raw)
    def client_factory():
        assert (tmp_path / "run-root/consumed" / (scope.run_id + ".json")).is_file()
        events.append("client")
        client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                             transport=httpx.MockTransport(lambda _: pytest.fail("unexpected HTTP")))
        clients.append(client)
        return client
    class Identities:
        failure_phase = None
        observed = None
        def __init__(self, **kwargs): self.ledger = kwargs["ledger"]
        async def capture_async(self, phase):
            events.append("identity/" + phase)
            for ordinal in range(4):
                ticket = self.ledger.begin(phase, ordinal, ["synthetic-process"], b"")
                self.ledger.finish(ticket, failed=False)
                if failure == "identity/" + phase and ordinal == 0:
                    self.failure_phase = "model_capture"
                    self.observed = scope.identity
                    raise r.p.ProtocolError("synthetic_failure")
            return scope.identity or prepared.identity
    class Inventories:
        def __init__(self, **kwargs): self.ledger = kwargs["ledger"]
        async def capture_async(self, phase):
            events.append("inventory/" + phase)
            kind = "preparationMetadata" if phase == "preparation" else "metadata"
            for ordinal in range(3):
                ticket = self.ledger.begin(kind, f"inventory/{phase}/metadata/{ordinal}", b"")
                self.ledger.finish(ticket, "completed", 200)
            kind = "snapshotPreparation" if phase == "preparation" else "snapshotPrePost"
            for ordinal in range(2):
                ticket = self.ledger.begin(kind, f"inventory/{phase}/{ordinal}", b"")
                self.ledger.finish(ticket, "completed", 200)
            if failure == "inventory/" + phase:
                raise r.p.ProtocolError("synthetic_failure")
            return scope.inventory or prepared.inventory
    prepared = scope if scope.phase == "execution" else _prepared(scope)
    monkeypatch.setattr(r, "IdentitySession", Identities)
    monkeypatch.setattr(r, "InventorySession", Inventories)
    class FakeRuntime:
        def __init__(self, **kwargs): self.kw = kwargs
        async def evaluate(self, *, cancellation):
            events.append("runtime")
            try:
                if failure == "runtime":
                    raise r.p.ProtocolError("synthetic_failure")
                await self.kw["postcheck"]()
                # Stage content is covered by the separate actual-runtime fake
                # integration below, not invented by this serial ordering test.
                return "synthetic-runtime-order-only"
            finally:
                self.kw["inventory_client"].close()
                self.kw["journal"].seal_cleanup(CleanupReport(True, True, True, True))
    monkeypatch.setattr(r, "OwnedComparisonRuntime", FakeRuntime)
    if actual_runtime:
        def runtime_factory(**kwargs):
            value, *resources = wire(monkeypatch, kwargs["pair"], kwargs["journal"])
            value.postcheck = kwargs["postcheck"]
            value.inventory_client = kwargs["inventory_client"]
            return value
        monkeypatch.setattr(r, "OwnedComparisonRuntime", runtime_factory)
    runner = r.IndependentRunner(scope=scope, authorization=scope.material(), confirm=confirmed,
        process=lambda *_: pytest.fail("unmocked process"), client=client_factory, synthetic_root=tmp_path / "run-root")
    return runner, events, clients, logs


def _prepared(scope):
    material = r.p.canonical({"synthetic": True})
    inventory = b'{"records":[{"id":"synthetic-only"}]}\n'
    return replace(scope, phase="execution", identity=IdentityCapture(sha256(STATIC).hexdigest(), "1" * 64,
        sha256(material).hexdigest(), material), inventory=InventoryCapture(BINDING, "2" * 64, 3, "3" * 64,
        sha256(inventory).hexdigest(), (), inventory))


async def test_serial_execution_consumes_before_providers_and_closes(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    result = await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events == ["confirmed", "client", "identity/pre", "inventory/pre", "runtime",
                      "identity/post", "inventory/post"]
    assert result.quality_assessment == "Not assessed" and not result.release_allowed
    assert all(client.is_closed for client in clients) and all(log.closed for log in logs)
    assert logs[0].identity_ledger.view()["counts"] == {"pre": 4, "post": 4}
    assert logs[0].ledger.counts["snapshotPrePost"] == 4
    with pytest.raises(r.p.ProtocolError, match="runner_already_attempted"):
        await runner.evaluate(cancellation=ManualCancellationSignal())


async def test_preparation_has_own_scope_and_no_runtime(scope, monkeypatch, tmp_path):
    scope = replace(scope, phase="preparation", inventory=None, identity=None)
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    result = await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events == ["confirmed", "client", "identity/preparation", "inventory/preparation"]
    assert result.comparison is None and all(client.is_closed for client in clients)
    assert logs[0].identity_ledger.view()["counts"] == {"preparation": 4}
    assert dict(scope.limits())["typedSearch"] == dict(scope.limits())["rerank"] == 0


@pytest.mark.parametrize("failure", ["identity/pre", "inventory/pre", "runtime", "identity/post", "inventory/post"])
async def test_stage_failure_stops_serial_progress_and_leaves_consumed(scope, monkeypatch, tmp_path, failure):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path, failure=failure)
    with pytest.raises(r.p.ProtocolError, match="runner_attempt_failed"):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events[-1] == failure
    assert all(client.is_closed for client in clients) and all(log.closed for log in logs)
    assert logs[0].ledger.view()["stopped"] and logs[0].identity_ledger.view()["stopped"]
    if failure.startswith("identity/"):
        assert runner.identity_failure_phase == "model_capture"
        assert runner.identity_failure_capture == scope.identity
    else:
        assert runner.identity_failure_phase is None and runner.identity_failure_capture is None
    replacement, *_ = setup(monkeypatch, scope, tmp_path)
    with pytest.raises(r.p.ProtocolError, match="runner_attempt_failed"):
        await replacement.evaluate(cancellation=ManualCancellationSignal())


@pytest.mark.parametrize("invalid", ["approved", "hash", "reference", "provenance"])
async def test_self_asserted_or_mismatched_confirmation_zero_operation(scope, monkeypatch, tmp_path, invalid):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    valid = receipt(scope, scope.material())
    runner.confirm = lambda _: ({"approved": True} if invalid == "approved" else replace(valid,
        **{"hash": {"authorization_sha256": "0" * 64}, "reference": {"reference": "P3_00:GATE-079"},
           "provenance": {"decision_record_sha256": ""}}[invalid]))
    with pytest.raises(r.p.ProtocolError, match="runner_attempt_failed"):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert not events and not clients and not logs and not (tmp_path / "run-root").exists()


@pytest.mark.parametrize("mutation", ["approved", "budget", "target", "window", "duplicate"])
def test_authorization_is_exact_scope_not_hash_self_approval(scope, tmp_path, mutation):
    value = json.loads(scope.material())
    if mutation == "approved": value["approved"] = True
    elif mutation == "budget": value["httpLimits"]["typedSearch"] += 1
    elif mutation == "target": value["target"]["index_name"] = "other"
    elif mutation == "window": value["window"]["expiresAt"] += 1
    raw = (scope.material().rstrip()[:-1] + b',"phase":"execution"}\n'
           if mutation == "duplicate" else r.p.canonical(value))
    with pytest.raises(r.p.ProtocolError, match="runner_authorization_mismatch"):
        r.IndependentRunner(scope=scope, authorization=raw, confirm=lambda _: receipt(scope, raw),
            process=lambda *_: b"", client=lambda: None, synthetic_root=tmp_path)


@pytest.mark.parametrize("now", [89, 110, 111])
async def test_invalid_window_zero_operation(scope, monkeypatch, tmp_path, now):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    monkeypatch.setattr(r.time, "time", lambda: now)
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert not events and not clients and not logs


async def test_static_drift_before_consumption_zero_operation(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    monkeypatch.setattr(r, "capture_static_identity", lambda *_: b"changed")
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events == ["confirmed"] and not clients and not logs
    assert not (tmp_path / "run-root").exists()


def test_live_root_cannot_be_relocated(scope, tmp_path):
    live = replace(scope, run_id="knowledge-document-number-20261004-01", evidence_kind="live_attempts")
    with pytest.raises(r.p.ProtocolError, match="runner_live_root_fixed"):
        r.IndependentRunner(scope=live, authorization=live.material(), confirm=lambda _: None,
            process=lambda *_: b"", client=lambda: None, synthetic_root=tmp_path)
    runner = r.IndependentRunner(scope=live, authorization=live.material(), confirm=lambda _: None,
                                 process=lambda *_: b"", client=lambda: None)
    assert runner.root == r._ROOT  # Do not evaluate a live scope in this test.


async def test_fsync_failure_retains_claim_and_calls_no_provider(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    monkeypatch.setattr(r.os, "fsync", lambda _: (_ for _ in ()).throw(OSError("private-error")))
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events == ["confirmed"] and not clients and not logs
    assert (tmp_path / "run-root/consumed" / (scope.run_id + ".json")).is_file()


def test_atomic_claim_concurrent_once(scope, tmp_path):
    barrier = Barrier(2)
    def attempt():
        barrier.wait()
        try:
            return r._consume(tmp_path / "root", scope, scope.material(), receipt(scope, scope.material()))
        except r.p.ProtocolError:
            return None
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: attempt(), range(2)))
    assert sum(outcome is not None for outcome in outcomes) == 1
    assert len(list((tmp_path / "root/consumed").iterdir())) == 1


async def test_actual_owned_runtime_with_outer_pre_and_post_and_shared_journal(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path, actual_runtime=True)
    # Native port and proxy startup seams are replaced, not real sockets/PIDs.
    from tests.evaluation.knowledge import rebuild_document_number_owned as owned
    from tests.evaluation.knowledge import rebuild_document_number_proxy as proxy
    monkeypatch.setattr(owned.shared, "_port_guard", lambda _: None)
    monkeypatch.setattr(proxy.ThreadingHTTPServer, "__init__", lambda *args, **kwargs: pytest.fail("real proxy"))
    result = await runner.evaluate(cancellation=ManualCancellationSignal())
    assert type(result.comparison) is runtime.OwnedComparisonCapture
    assert len(result.comparison.stage.cases) == 10 and len(result.comparison.stage.physical_witnesses) == 44
    assert logs[0].ledger.counts == {"snapshotPreparation": 0, "preparationMetadata": 0,
        "snapshotPrePost": 4, "metadata": 18, "physicalSearch": 44, "typedSearch": 44,
        "queryEmbedding": 10, "rerank": 22, "prewarmRerank": 1, "javaHealth": 2, "bgeHealth": 0}
    assert logs[0].identity_ledger.view()["counts"] == {"pre": 4, "post": 4}
    assert all(client.is_closed for client in clients) and scope.pair.resources_released and logs[0].closed
    assert events[-2:] == ["identity/post", "inventory/post"]
    assert not result.release_allowed and result.quality_assessment == "Not assessed"


async def test_cancel_before_confirmation_does_not_consume(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    signal = ManualCancellationSignal()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    with pytest.raises(asyncio.CancelledError):
        await runner.evaluate(cancellation=signal)
    assert not events and not clients and not logs


async def test_both_stop_categories_attempted_when_first_checkpoint_fails(tmp_path):
    from tests.evaluation.knowledge.rebuild_document_number_journal import JournalBinding
    with AttemptJournal(directory=tmp_path / "synthetic-document-number-009", binding=JournalBinding(
        "synthetic-document-number-009", "f" * 40, "1" * 64, "2" * 64, "3" * 64, "4" * 64,
        "synthetic_non_live"), limits=(("metadata", 1),), identity_phases=("pre", "post")) as log:
        log.ledger._writer = lambda *_: (_ for _ in ()).throw(OSError("private"))
        assert not r._stop(log)
        assert log.ledger.view()["stopped"] and log.identity_ledger.view()["stopped"]


@pytest.mark.parametrize("stop_at", [1, 2])
async def test_window_expiry_before_each_proxy_never_starts_next(scope, monkeypatch, tmp_path, stop_at):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path, actual_runtime=True)
    from tests.evaluation.knowledge import rebuild_document_number_owned as owned
    from tests.evaluation.knowledge import rebuild_document_number_proxy as proxy
    monkeypatch.setattr(owned.shared, "_port_guard", lambda _: None)
    starts, java_starts = [], []
    factory = r.OwnedComparisonRuntime
    def guarded_factory(**kwargs):
        value = factory(**kwargs)
        checked = 0
        def window():
            nonlocal checked
            checked += 1
            if checked == stop_at:
                raise r.p.ProtocolError("runner_window_invalid")
        kwargs["journal"]._operation_guard = window
        old_start = proxy.DocumentNumberProxy.start
        monkeypatch.setattr(proxy.DocumentNumberProxy, "start", lambda self: starts.append(self) or old_start(self))
        old_popen = owned.subprocess.Popen
        monkeypatch.setattr(owned.subprocess, "Popen", lambda *args, **kw: java_starts.append(args) or old_popen(*args, **kw))
        return value
    monkeypatch.setattr(r, "OwnedComparisonRuntime", guarded_factory)
    with pytest.raises(r.p.ProtocolError, match="runner_attempt_failed"):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert len(starts) == stop_at - 1 and not java_starts
    assert logs[0].ledger.counts["typedSearch"] == logs[0].ledger.counts["javaHealth"] == 0
    assert "identity/post" not in events and all(client.is_closed for client in clients)
    assert scope.pair.resources_released and logs[0].closed


async def test_expiry_between_identity_probes_stops_before_next_provider(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    original = r.IdentitySession
    class Expiring(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            calls = 0
            def guard():
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise r.p.ProtocolError("runner_window_invalid")
            # Both ledger guards come from the same owning journal.
            logs[0]._operation_guard = guard
    monkeypatch.setattr(r, "IdentitySession", Expiring)
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert events == ["confirmed", "client", "identity/pre"]
    assert logs[0].identity_ledger.view()["counts"] == {"pre": 2, "post": 0}
    assert logs[0].identity_ledger.view()["pending"] == 1  # Rejected checkpoint is not a completed probe.
    assert logs[0].closed and all(client.is_closed for client in clients)


async def test_cancel_drains_late_phase_and_never_runs_inventory_or_runtime(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    started, drained, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = r.IdentitySession
    class Slow(original):
        async def capture_async(self, phase):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                # A bounded provider may complete late; the outer boundary
                # must wait, reject that success and keep its client alive.
                await release.wait()
                assert not clients[0].is_closed
                drained.set()
                return scope.identity
    monkeypatch.setattr(r, "IdentitySession", Slow)
    signal = ManualCancellationSignal()
    task = asyncio.create_task(runner.evaluate(cancellation=signal))
    await started.wait()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done() and not clients[0].is_closed
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained.is_set() and clients[0].is_closed and logs[0].closed
    assert "runtime" not in events and "inventory/pre" not in events


async def test_stop_checkpoint_failure_still_drains_and_closes(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    started, drained = asyncio.Event(), asyncio.Event()
    original = r.IdentitySession
    class Slow(original):
        async def capture_async(self, phase):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                assert not clients[0].is_closed
                drained.set()
                raise
    monkeypatch.setattr(r, "IdentitySession", Slow)
    signal = ManualCancellationSignal()
    task = asyncio.create_task(runner.evaluate(cancellation=signal))
    await started.wait()
    logs[0].ledger._writer = lambda *_: (_ for _ in ()).throw(OSError("private"))
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    with pytest.raises(r.p.ProtocolError):
        await task
    assert drained.is_set() and clients[0].is_closed and logs[0].closed
    assert logs[0].ledger.view()["stopped"] and logs[0].identity_ledger.view()["stopped"]


async def test_short_consumption_write_remains_consumed_zero_provider(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    original = Path.open
    class Short:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def write(self, raw): return self.stream.write(raw[:10])
        def flush(self): return self.stream.flush()
        def fileno(self): return self.stream.fileno()
    def open_file(path, mode="r", *args, **kwargs):
        stream = original(path, mode, *args, **kwargs)
        return Short(stream) if path.parent.name == "consumed" and mode == "xb" else stream
    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    marker = tmp_path / "run-root/consumed" / (scope.run_id + ".json")
    assert marker.stat().st_size == 10 and events == ["confirmed"] and not clients and not logs


def test_path_alias_cannot_create_another_claim(scope, tmp_path):
    root = tmp_path / "actual"
    root.mkdir()
    with pytest.raises(r.p.ProtocolError, match="runner_path_invalid"):
        r._consume(root / ".." / "actual", scope, scope.material(), receipt(scope, scope.material()))
    assert not (root / "consumed").exists()


async def test_rejected_client_subclass_is_owned_and_closed(scope, monkeypatch, tmp_path):
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    class Unsupported(httpx.Client):
        pass
    returned = Unsupported(base_url="http://127.0.0.1:9200", trust_env=False,
                           transport=httpx.MockTransport(lambda _: pytest.fail("HTTP prohibited")))
    runner.client_factory = lambda: returned
    with pytest.raises(r.p.ProtocolError):
        await runner.evaluate(cancellation=ManualCancellationSignal())
    assert returned.is_closed and logs[0].closed
    assert logs[0].ledger.view()["counts"] == dict.fromkeys(dict(scope.limits()), 0)
    closed = json.loads(logs[0]._path.read_text(encoding="utf-8").splitlines()[-1])
    assert closed["reportedCleanup"]["clients_closed"] is True


async def test_actual_identity_worker_checks_signal_before_next_probe_even_without_watcher(scope, monkeypatch, tmp_path):
    from tests.evaluation.knowledge import rebuild_document_number_identity as identity_module
    from tests.evaluation.knowledge.test_rebuild_document_number_identity import model_fixture, Provider
    model, embedding, rerank = model_fixture(tmp_path)
    scope = replace(scope, phase="preparation", model=model, identity=None, inventory=None)
    runner, events, clients, logs = setup(monkeypatch, scope, tmp_path)
    monkeypatch.setattr(r, "IdentitySession", identity_module.IdentitySession)
    monkeypatch.setattr(identity_module, "capture_static_identity", lambda *_: STATIC)
    # Delay watcher notification deliberately. Provider threads must still
    # observe the cancellation flag at their own next operation boundary.
    class DeferredSignal:
        cancelled = False
        def is_cancelled(self): return self.cancelled
        async def wait_cancelled(self): await asyncio.Future()
    signal = DeferredSignal()
    provider = Provider(model, embedding, rerank)
    def process(command, raw):
        result = provider(command, raw)
        signal.cancelled = True
        return result
    runner.process = process
    with pytest.raises((r.p.ProtocolError, asyncio.CancelledError)):
        await runner.evaluate(cancellation=signal)
    assert len(provider.calls) == 1 and clients[0].is_closed and logs[0].closed
    assert "inventory/preparation" not in events and "runtime" not in events
    assert logs[0].identity_ledger.view()["stopped"] and logs[0].ledger.view()["stopped"]
