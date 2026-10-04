"""Fake client/HTTP handler/lifecycle checks; never open a listener or use ES."""
from dataclasses import asdict
from email.message import Message
from hashlib import sha256
from io import BytesIO
import socket
import subprocess
from threading import Event, Thread
from types import SimpleNamespace
import traceback

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_proxy as x
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_transport import AttemptLedger
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding
from tests.evaluation.knowledge.rebuild_document_number_stage import StageComparisonSession
from tests.evaluation.knowledge.test_rebuild_document_number_owned import pair
from tests.evaluation.knowledge.test_rebuild_document_number_stage import Scripted
from tests.evaluation.knowledge.test_rebuild_document_number_transport import (
    draft, physical, synthetic_keyword_hashes,
)

BINDING = ReadBinding("synthetic-read", "synthetic-index", "synthetic-uuid", "synthetic-v1")


@pytest.fixture(autouse=True)
def no_real_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real resource acquisition attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    # Windows asyncio legitimately uses a local socketpair internally. Block
    # native HTTP sends instead of breaking the event loop's own wakeup pipe.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(x.ThreadingHTTPServer, "__init__", forbidden)


def raw_response(body=b"{}", *, status=200, headers=None):
    return httpx.Response(status, headers={"Content-Type": "application/json",
        "X-Elastic-Product": "Elasticsearch", **(headers or {})}, stream=httpx.ByteStream(body))


def metadata():
    return (p.canonical({BINDING.index_name: {"aliases": {BINDING.read_alias: {}}}}),
        p.canonical({BINDING.index_name: {"settings": {"index": {"uuid": BINDING.index_uuid}}}}),
        p.canonical({BINDING.index_name: {"mappings": {"_meta": {"mapping_version": BINDING.mapping_version}}}}))


def make(draft, handler=None, *, arm="old"):
    paths, responses = x.metadata_paths(BINDING), metadata()
    hashes = tuple((path, sha256(raw).hexdigest()) for path, raw in zip(paths, responses, strict=True))
    calls = []
    def respond(request):
        calls.append(request)
        if handler is not None:
            return handler(request)
        return raw_response(dict(zip(paths, responses)).get(request.url.path,
            p.canonical({"hits": {"hits": []}})))
    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                           transport=httpx.MockTransport(respond))
    ledger = AttemptLedger((("metadata", 12), ("physicalSearch", 44)))
    proxy = x.DocumentNumberProxy(draft=draft, arm=arm, port=19321, binding=BINDING,
                                  metadata_sha256=hashes, ledger=ledger, backend=backend)
    return proxy, backend, ledger, calls


def ready(proxy):
    for _ in range(2):
        for path in proxy.hashes:
            assert proxy.forward("GET", path, b"").status_code == 200


@pytest.mark.parametrize("arm", p.ARMS)
def test_two_profile_metadata_then_exact_all_cases_original_bytes_and_finite_receipts(draft, arm):
    proxy, backend, ledger, calls = make(draft, arm=arm)
    try:
        ready(proxy)
        for case in draft.cases:
            hashes = synthetic_keyword_hashes(case)
            proxy.bind(case=case, vector=(0.0,) * 1024, keyword_sha256=hashes)
            for item in reversed(case.plan.items):
                body = p.canonical(physical(case, route=item.path.value, domain=item.logical_domain_id))
                assert proxy.forward("POST", "/synthetic-read/_search", body).status_code == 200
                assert calls[-1].content == body
            receipts = proxy.finish()
            assert [(row.domain, row.path) for row in receipts] == [
                (item.logical_domain_id, item.path.value) for item in case.plan.items]
            assert all(row.arm == arm and row.case_id == case.case_id for row in receipts)
        assert len(calls) == 28 and ledger.counts == {"metadata": 6, "physicalSearch": 22}
        assert proxy.completed_cases == 10 and proxy.violations == ledger.view()["pending"] == 0
        finite = p.canonical([asdict(row) for row in receipts]).decode()
        assert "query_vector" not in finite and draft.cases[-1].plan.original_question not in finite
    finally:
        proxy.close()
        backend.close()


@pytest.mark.parametrize("method,path,body", [("GET", "/_cluster/health", b""),
    ("GET", "/synthetic-index/_mapping?filter_path=*", b""), ("PUT", "/_aliases", b"{}"),
    ("DELETE", "/synthetic-index", b""), ("POST", "/other/_search", b"{}"),
    ("POST", "/synthetic-read/_search", b"{}"), ("GET", "/_alias/synthetic-read", b"{}")])
def test_route_violation_zero_send_stops_whole_ledger(draft, method, path, body):
    proxy, backend, ledger, calls = make(draft)
    try:
        with pytest.raises(p.ProtocolError, match="proxy_forward_failed"):
            proxy.forward(method, path, body)
        assert not calls and not any(ledger.counts.values()) and ledger.view()["stopped"]
        with pytest.raises(p.ProtocolError):
            proxy.forward("GET", next(iter(proxy.hashes)), b"")
        assert not calls
    finally:
        proxy.close()
        backend.close()


def test_third_startup_get_and_case_without_completed_profiles_are_rejected(draft):
    proxy, backend, ledger, calls = make(draft)
    try:
        case = draft.cases[0]
        with pytest.raises(p.ProtocolError, match="case_binding_invalid"):
            proxy.bind(case=case, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(case))
        path = next(iter(proxy.hashes))
        proxy.forward("GET", path, b"")
        proxy.forward("GET", path, b"")
        with pytest.raises(p.ProtocolError):
            proxy.forward("GET", path, b"")
        assert len(calls) == ledger.counts["metadata"] == 2 and ledger.view()["stopped"]
    finally:
        proxy.close()
        backend.close()


@pytest.mark.parametrize("response", ["changed", "duplicate", "bad_media", "encoding", "product", "length", "deadline", "http", "transport"])
def test_response_or_metadata_drift_is_charged_once_never_retried_or_leaked(draft, monkeypatch, response):
    def handler(request):
        if response == "transport":
            raise httpx.ReadError("synthetic-private-provider")
        headers = {"bad_media": {"Content-Type": "text/html"}, "encoding": {"Content-Encoding": "gzip"},
            "product": {"X-Elastic-Product": "other"}, "length": {"Content-Length": str(x._MAX + 1)}}.get(response)
        return raw_response(b'{"a":1,"a":2}' if response == "duplicate" else b"{}",
                            status=503 if response == "http" else 200, headers=headers)
    proxy, backend, ledger, calls = make(draft, handler)
    try:
        if response == "deadline":
            times = iter((0, 11))
            monkeypatch.setattr(x.time, "monotonic", lambda: next(times, 11))
        with pytest.raises(p.ProtocolError, match="proxy_forward_failed") as caught:
            proxy.forward("GET", next(iter(proxy.hashes)), b"")
        assert len(calls) == ledger.counts["metadata"] == 1 and ledger.view()["pending"] == 0
        assert ledger.view()["stopped"] and "synthetic-private-provider" not in "".join(traceback.format_exception(caught.value))
        assert caught.value.__suppress_context__
    finally:
        proxy.close()
        backend.close()


@pytest.mark.parametrize("violation", ["retry", "metadata_after_bind"])
def test_case_order_missing_receipt_rebind_retry_and_metadata_after_bind(draft, violation):
    proxy, backend, ledger, calls = make(draft)
    try:
        ready(proxy)
        first, second = draft.cases[:2]
        with pytest.raises(p.ProtocolError):
            proxy.bind(case=second, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(second))
        proxy.bind(case=first, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(first))
        with pytest.raises(p.ProtocolError, match="case_incomplete"):
            proxy.finish()
        with pytest.raises(p.ProtocolError):
            proxy.bind(case=first, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(first))
        body = p.canonical(physical(first))
        proxy.forward("POST", "/synthetic-read/_search", body)
        with pytest.raises(p.ProtocolError):
            if violation == "retry":
                proxy.forward("POST", "/synthetic-read/_search", body)
            else:
                proxy.forward("GET", next(iter(proxy.hashes)), b"")
        assert ledger.counts["physicalSearch"] == 1 and ledger.view()["stopped"]
    finally:
        proxy.close()
        backend.close()


def test_parallel_path_io_not_serialized_and_finish_forbidden_until_receipts(draft):
    entered, release = Event(), Event()
    def handler(request):
        if request.method == "GET":
            return raw_response(dict(zip(x.metadata_paths(BINDING), metadata()))[request.url.path])
        if b'"query"' in request.content:
            entered.set()
            assert release.wait(timeout=2)
        return raw_response(p.canonical({"hits": {"hits": []}}))
    proxy, backend, ledger, calls = make(draft, handler)
    errors = []
    try:
        ready(proxy)
        case = draft.cases[0]
        proxy.bind(case=case, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(case))
        def keyword():
            try:
                proxy.forward("POST", "/synthetic-read/_search", p.canonical(physical(case)))
            except Exception as error:
                errors.append(type(error))
        thread = Thread(target=keyword)
        thread.start()
        assert entered.wait(timeout=2)
        proxy.forward("POST", "/synthetic-read/_search", p.canonical(physical(case, route="vector")))
        with pytest.raises(p.ProtocolError):
            proxy.finish()
        release.set()
        thread.join(timeout=2)
        assert not thread.is_alive() and not errors and len(proxy.finish()) == 2
    finally:
        release.set()
        proxy.close()
        backend.close()


@pytest.mark.parametrize("failure", [None, "thread_start", "close"])
def test_listener_owned_before_thread_start_and_partial_failure_cleanup(monkeypatch, draft, failure):
    created = []
    def server_init(self, address, handler):
        self.address, self.handler, self.actions = address, handler, []
        created.append(self)
    def server_close(self):
        self.actions.append("close")
        if failure == "close":
            raise OSError("synthetic-private-close")
    monkeypatch.setattr(x.ThreadingHTTPServer, "__init__", server_init)
    monkeypatch.setattr(x.ThreadingHTTPServer, "serve_forever", lambda self: None)
    monkeypatch.setattr(x.ThreadingHTTPServer, "server_close", server_close)
    monkeypatch.setattr(x.ThreadingHTTPServer, "shutdown", lambda self: self.actions.append("shutdown"))
    class FakeThread:
        ident = None
        def __init__(self, **kwargs):
            self.started = False
        def start(self):
            if failure == "thread_start":
                raise RuntimeError("synthetic-private-start")
            self.started, self.ident = True, 1
        def is_alive(self):
            return self.started
        def join(self, timeout):
            self.started = False
    monkeypatch.setattr(x, "Thread", FakeThread)
    proxy, backend, ledger, calls = make(draft)
    try:
        if failure == "thread_start":
            with pytest.raises(p.ProtocolError, match="proxy_start_failed"):
                proxy.start()
        else:
            proxy.start()
        assert proxy.server is created[0] and created[0].address == ("127.0.0.1", 19321)
        with pytest.raises(p.ProtocolError, match="proxy_start_invalid"):
            proxy.start()
        if failure == "close":
            with pytest.raises(p.ProtocolError, match="proxy_cleanup_failed") as caught:
                proxy.close()
            assert not proxy.closed and "synthetic-private-close" not in "".join(traceback.format_exception(caught.value))
        else:
            proxy.close()
            assert proxy.closed and created[0].actions[-1] == "close"
        assert not calls
    finally:
        backend.close()


@pytest.mark.parametrize("change", [None, "duplicate_length", "chunked", "oversize", "incomplete", "unknown_verb",
                                    "requestline_timeout", "header_timeout"])
def test_real_handler_framing_and_unsupported_verbs_fail_closed_without_listener(monkeypatch, draft, change):
    captured = []
    monkeypatch.setattr(x.ThreadingHTTPServer, "__init__", lambda self, address, handler: captured.append(handler))
    monkeypatch.setattr(x.ThreadingHTTPServer, "serve_forever", lambda self: None)
    monkeypatch.setattr(x.ThreadingHTTPServer, "server_close", lambda self: None)
    class FakeThread:
        ident = None
        def __init__(self, **kwargs): pass
        def start(self): pass
        def is_alive(self): return False
    monkeypatch.setattr(x, "Thread", FakeThread)
    proxy, backend, ledger, calls = make(draft)
    try:
        proxy.start()
        handler = captured[0].__new__(captured[0])
        handler.headers = Message()
        body = b"" if change != "incomplete" else b"x"
        handler.headers.add_header("Content-Length", "0" if change != "incomplete" else "2")
        if change == "duplicate_length":
            handler.headers.add_header("Content-Length", "0")
        if change == "chunked":
            handler.headers.add_header("Transfer-Encoding", "chunked")
        if change == "oversize":
            handler.headers.replace_header("Content-Length", str(x._MAX + 1))
        handler.connection = SimpleNamespace(settimeout=lambda value: None)
        handler.rfile, handler.wfile = BytesIO(body), BytesIO()
        handler.path, handler.command = next(iter(proxy.hashes)), "GET"
        responses = []
        handler.send_response = lambda status, *args: responses.append(status)
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        if change in ("requestline_timeout", "header_timeout"):
            class TimeoutInput(BytesIO):
                def readline(self, *args):
                    if change == "header_timeout" and self.tell() == 0:
                        return super().readline(*args)
                    raise TimeoutError("synthetic-private-input")
            handler.rfile = TimeoutInput(b"GET /_alias/synthetic-read HTTP/1.0\r\n")
            handler.handle_one_request()
            assert handler.close_connection and responses == []
            with pytest.raises(p.ProtocolError, match="proxy_forward_failed"):
                proxy.forward("GET", handler.path, b"")
        elif change == "unknown_verb":
            handler.send_error(501, "synthetic-private-input", "synthetic-private-input")
        else:
            handler.do_GET()
        if change is None:
            assert responses == [200] and len(calls) == ledger.counts["metadata"] == 1
            assert handler.wfile.getvalue() == metadata()[0] and proxy.violations == 0
        else:
            assert responses == ([] if change in ("requestline_timeout", "header_timeout") else
                                  [501 if change == "unknown_verb" else 502])
            assert not calls and not any(ledger.counts.values()) and ledger.view()["stopped"]
            assert b"synthetic-private-input" not in handler.wfile.getvalue()
    finally:
        proxy.close()
        backend.close()


def test_owned_accepted_socket_is_interrupted_before_joining_handler_threads(monkeypatch, draft):
    events = []
    class Connection:
        def shutdown(self, how): events.append(("socket_shutdown", how))
        def close(self): events.append("socket_close")
    class Server:
        def shutdown(self): events.append("server_shutdown")
        def server_close(self): events.append("join_handlers")
    class FakeThread:
        ident = 1
        def is_alive(self): return False
        def join(self, timeout): events.append("join_listener")
    proxy, backend, ledger, calls = make(draft)
    try:
        proxy._connections.add(Connection())
        proxy.server, proxy.thread = Server(), FakeThread()
        proxy.close()
        assert events == [("socket_shutdown", socket.SHUT_RDWR), "socket_close", "join_handlers", "join_listener"]
        assert proxy.closed and not calls and not backend.is_closed
    finally:
        backend.close()


@pytest.mark.parametrize("change", ["cookies", "auth", "hooks", "redirect_origin", "retry", "params"])
def test_backend_guard_not_bypassed_by_proxy_after_client_mutation(draft, change):
    proxy, backend, ledger, calls = make(draft)
    try:
        if change == "cookies": backend.cookies.set("session", "synthetic-private")
        if change == "auth": backend.auth = ("synthetic", "synthetic")
        if change == "hooks": backend.event_hooks = {"request": [lambda req: None], "response": []}
        if change == "redirect_origin": backend.base_url = "http://other.invalid"
        if change == "params": backend.params = {"routing": "synthetic-subset"}
        if change == "retry":
            class CustomTransport(httpx.MockTransport): pass
            backend._transport = CustomTransport(lambda req: raw_response())
        with pytest.raises(p.ProtocolError, match="proxy_forward_failed"):
            proxy.forward("GET", next(iter(proxy.hashes)), b"")
        assert not calls and ledger.counts["metadata"] == 1 and ledger.view()["pending"] == 0
    finally:
        proxy.close()
        backend.close()


def test_default_query_params_added_after_ready_are_rejected_before_physical_send(draft):
    proxy, backend, ledger, calls = make(draft)
    try:
        ready(proxy)
        case = draft.cases[0]
        proxy.bind(case=case, vector=(0.0,) * 1024, keyword_sha256=synthetic_keyword_hashes(case))
        backend.params = {"routing": "synthetic-subset"}
        with pytest.raises(p.ProtocolError, match="proxy_forward_failed"):
            proxy.forward("POST", "/synthetic-read/_search", p.canonical(physical(case)))
        assert len(calls) == 6 and ledger.counts["physicalSearch"] == 1
        assert ledger.view()["pending"] == 0 and ledger.view()["stopped"]
        assert proxy.completed_cases == 0
    finally:
        proxy.close()
        backend.close()


async def test_full_production_stage_uses_both_real_proxy_ports_and_shared_journal_fake_only(pair, tmp_path):
    from agent_runtime.capability_api.contracts import OpaqueUserToken
    from tests.helpers import ManualCancellationSignal
    binding = JournalBinding("synthetic-document-number-003", "f" * 40, "1" * 64, "2" * 64,
                             "3" * 64, "4" * 64, "synthetic_non_live")
    with AttemptJournal(directory=tmp_path / binding.run_id, binding=binding,
        limits=(("metadata", 12), ("typedSearch", 44), ("physicalSearch", 44),
                ("queryEmbedding", 10), ("rerank", 22))) as journal:
        proxies, backends = [], []
        try:
            for arm in p.ARMS:
                proxy, backend, _, calls = make(pair.draft, arm=arm)
                proxy.ledger = journal.ledger
                proxies.append(proxy)
                backends.append(backend)
                ready(proxy)
            class Bridge:
                # This bridge is a fake typed-service producer, not Java or a
                # physical permission bypass. All ES traffic reaches the port.
                def __init__(self, proxy): self.proxy, self.arm, self.gate = proxy, proxy.arm, self
                @property
                def case(self): return self.proxy.draft.cases[self.proxy.completed_cases]
                def forward(self, *, method, path, body, send): return self.proxy.forward(method, path, body)
            session = StageComparisonSession(pair=pair, ledger=journal.ledger,
                typed=tuple(Scripted(Bridge(proxy)) for proxy in proxies),
                embedding=Scripted(), rerank=Scripted(), physical=tuple(proxies))
            result = await session.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"),
                                            cancellation=ManualCancellationSignal())
            assert len(result.cases) == 10 and len(result.physical_witnesses) == 44
            assert journal.ledger.counts == {"metadata": 12, "typedSearch": 44, "physicalSearch": 44,
                                             "queryEmbedding": 10, "rerank": 22}
            assert all(proxy.completed_cases == 10 and proxy.violations == 0 for proxy in proxies)
            assert journal.ledger.view()["pending"] == 0 and result.quality_assessment == "Not assessed"
            assert "synthetic-memory-only" not in journal._path.read_text(encoding="utf-8")
        finally:
            for proxy in proxies: proxy.close()
            for backend in backends: backend.close()
