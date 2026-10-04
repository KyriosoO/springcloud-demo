"""Owned, read-only physical ES port for an independently authorized comparison.

No default listener/client, credential discovery, CLI or execution authority.
The caller owns the backend client and registers this proxy before ``start``.
Metadata expectations must come from the new frozen inventory, not old evidence.
Request/response bodies remain in memory; only the existing finite ledger emits.
"""
from __future__ import annotations

from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import socket
from threading import Lock, Thread
import time

import httpx

from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse
from knowledge_corpus_tools.http_client_safety import _single_send_client
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_transport import (
    AttemptLedger, PhysicalSearchGate, PhysicalWitness,
)

_MAX = 2 * 1024 * 1024


def metadata_paths(binding: ReadBinding) -> tuple[str, str, str]:
    binding.__post_init__()
    return (f"/_alias/{binding.read_alias}", f"/{binding.index_name}/_settings",
            f"/{binding.index_name}/_mapping")


def _backend_response(client: httpx.Client, method: str, path: str, body: bytes) -> BoundedHttpResponse:
    # Check on every send: no cookies/hooks/mount/auth/retry may multiply one
    # counted request. The caller-owned client is never closed by this port.
    p.require(_single_send_client(client) and str(client.base_url) in
              ("http://127.0.0.1:9200", "http://127.0.0.1:9200/"),
              "proxy_backend_invalid")
    deadline = time.monotonic() + 10
    with client.stream(method, path, content=body or None, timeout=5, follow_redirects=False,
        headers={"Accept-Encoding": "identity", "Content-Type": "application/json"}) as response:
        p.require(response.headers.get_list("x-elastic-product") == ["Elasticsearch"]
            and response.headers.get("content-encoding", "identity") == "identity"
            and response.headers.get("content-type", "").split(";", 1)[0].strip() == "application/json",
            "proxy_response_invalid")
        lengths = response.headers.get_list("content-length")
        p.require(not lengths or len(lengths) == 1 and lengths[0].isascii() and lengths[0].isdecimal()
                  and int(lengths[0]) <= _MAX, "proxy_response_length_invalid")
        data = bytearray()
        for part in response.iter_raw():
            p.require(time.monotonic() <= deadline and len(data) + len(part) <= _MAX,
                      "proxy_response_bound_exceeded")
            data.extend(part)
        p.require(time.monotonic() <= deadline and 0 < len(data) <= _MAX
                  and (not lengths or int(lengths[0]) == len(data)), "proxy_response_bound_exceeded")
        return BoundedHttpResponse(status_code=response.status_code, content_type="application/json",
                                   content_encoding=None, body=bytes(data))


class DocumentNumberProxy:
    """Two frozen startup Profiles, then one exact selected case at a time.

    Concurrent keyword/vector sends are not serialized across backend I/O.
    State transitions are locked; finish/rebind is forbidden while any send is
    in flight. A violation stops the shared ledger, including the other arm.
    """
    def __init__(self, *, draft: p.DraftProtocol, arm: str, port: int, binding: ReadBinding,
                 metadata_sha256: tuple[tuple[str, str], ...], ledger: AttemptLedger,
                 backend: httpx.Client) -> None:
        p.require(type(draft) is p.DraftProtocol and arm in p.ARMS and type(port) is int
                  and 1024 <= port <= 65535 and type(binding) is ReadBinding
                  and type(ledger) is AttemptLedger, "proxy_binding_invalid")
        draft.__post_init__()
        paths = metadata_paths(binding)
        p.require(type(metadata_sha256) is tuple and len(metadata_sha256) == 3
                  and tuple(path for path, _ in metadata_sha256) == paths
                  and all(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                          for _, digest in metadata_sha256), "proxy_metadata_binding_invalid")
        self.draft, self.arm, self.port, self.binding = draft, arm, port, binding
        self.ledger, self.backend = ledger, backend
        self.hashes = dict(metadata_sha256)
        self.metadata_counts = dict.fromkeys(paths, 0)
        self.completed_cases = 0
        self.violations = 0
        self._gate: PhysicalSearchGate | None = None
        self._inflight = 0
        self._lock = Lock()
        self._closing = self._closed = self._start_attempted = False
        self._connections: set[socket.socket] = set()
        self.server: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    def violate(self) -> None:
        with self._lock:
            self.violations += 1
        self.ledger.abort()

    def bind(self, *, case: p.ComparisonCase, vector: tuple[float, ...],
             keyword_sha256: tuple[tuple[str, str], ...]) -> None:
        with self._lock:
            p.require(not self._closing and not self.closed and not self.violations and self._inflight == 0
                and self._gate is None and self.completed_cases < len(self.draft.cases)
                and case == self.draft.cases[self.completed_cases]
                and all(count == 2 for count in self.metadata_counts.values())
                and not self.ledger.view()["stopped"], "proxy_case_binding_invalid")
            self._gate = PhysicalSearchGate(case=case, arm=self.arm, read_alias=self.binding.read_alias,
                vector=vector, ledger=self.ledger, keyword_sha256=keyword_sha256)

    def forward(self, method: str, path: str, body: bytes) -> BoundedHttpResponse:
        failed = False
        acquired = False
        result: BoundedHttpResponse | None = None
        try:
            p.require(type(body) is bytes and len(body) <= _MAX, "proxy_request_invalid")
            with self._lock:
                p.require(not self._closing and not self.closed and not self.violations
                          and not self.ledger.view()["stopped"], "proxy_stopped")
                if method == "GET" and path in self.hashes and not body:
                    p.require(self._gate is None and self.completed_cases == 0
                              and self.metadata_counts[path] < 2, "proxy_metadata_not_expected")
                    ordinal = self.metadata_counts[path]
                    self.metadata_counts[path] += 1
                    gate = None
                else:
                    p.require(method == "POST" and path == f"/{self.binding.read_alias}/_search"
                              and self._gate is not None, "proxy_route_forbidden")
                    gate = self._gate
                self._inflight += 1
                acquired = True
            if gate is None:
                ticket = self.ledger.begin("metadata", f"startup/{self.arm}/{ordinal}/{path.strip('/')}", b"")
                transport_failed = False
                try:
                    result = _backend_response(self.backend, method, path, body)
                except Exception:
                    transport_failed = True
                if transport_failed:
                    self.ledger.finish(ticket, "transport_failed")
                    raise p.ProtocolError("proxy_metadata_transport_failed")
                assert result is not None
                self.ledger.finish(ticket, "completed", result.status_code)
                p.require(result.status_code == 200
                    and sha256(p.canonical(p._decode(result.body))).hexdigest() == self.hashes[path],
                    "proxy_metadata_drift")
            else:
                result = gate.forward(method=method, path=path, body=body,
                    send=lambda original: _backend_response(self.backend, method, path, original))
        except Exception:
            failed = True
        finally:
            if acquired:
                with self._lock:
                    self._inflight -= 1
        if failed:
            self.violate()
            raise p.ProtocolError("proxy_forward_failed") from None
        assert result is not None
        return result

    def finish(self) -> tuple[PhysicalWitness, ...]:
        with self._lock:
            p.require(not self._closing and not self.closed and not self.violations and self._inflight == 0
                      and self._gate is not None and not self.ledger.view()["stopped"], "proxy_case_incomplete")
            gate = self._gate
            assert gate is not None
            order = {(item.logical_domain_id, item.path.value): n for n, item in enumerate(gate.case.plan.items)}
            rows = tuple(gate.witnesses)
            p.require(len(rows) == len(order) and all(row.http_status == 200 for row in rows)
                      and {(row.domain, row.path) for row in rows} == set(order), "proxy_case_incomplete")
            self._gate = None
            self.completed_cases += 1
            return tuple(sorted(rows, key=lambda row: order[(row.domain, row.path)]))

    def start(self) -> None:
        p.require(not self._start_attempted and not self.closed and not self._closing, "proxy_start_invalid")
        self._start_attempted = True
        owner = self

        class Server(ThreadingHTTPServer):
            daemon_threads = False
            block_on_close = True
            def process_request(self, request: socket.socket | tuple[bytes, socket.socket],
                                client_address: object) -> None:
                p.require(isinstance(request, socket.socket), "proxy_socket_invalid")
                assert isinstance(request, socket.socket)
                with owner._lock:
                    closing = owner._closing
                    if not closing:
                        owner._connections.add(request)
                if closing:
                    self.close_request(request)
                    return
                super().process_request(request, client_address)

            def close_request(self, request: socket.socket | tuple[bytes, socket.socket]) -> None:
                p.require(isinstance(request, socket.socket), "proxy_socket_invalid")
                assert isinstance(request, socket.socket)
                with owner._lock:
                    owner._connections.discard(request)
                super().close_request(request)

            def handle_error(self, request: object, client_address: object) -> None:
                # Provider/handler tracebacks may contain private response data.
                owner.violate()

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(6)

            def log_message(self, format: str, *args: object) -> None:
                pass

            def log_error(self, format: str, *args: object) -> None:
                # BaseHTTPRequestHandler consumes request-line/header socket
                # timeouts via log_error, without calling our route/send_error.
                owner.violate()

            def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
                # Includes unsupported verbs and malformed header/request lines
                # handled by BaseHTTPRequestHandler before our route function.
                owner.violate()
                super().send_error(code, "Controlled request failed", "")

            def do_GET(self) -> None:
                self.forward("GET")

            def do_POST(self) -> None:
                self.forward("POST")

            def do_PUT(self) -> None:
                self.forward("PUT")

            def do_DELETE(self) -> None:
                self.forward("DELETE")

            def forward(self, method: str) -> None:
                try:
                    lengths = self.headers.get_all("Content-Length", [])
                    p.require(len(lengths) <= 1 and not self.headers.get_all("Transfer-Encoding"), "proxy_length_invalid")
                    length = lengths[0] if lengths else "0"
                    p.require(length.isascii() and length.isdecimal() and int(length) <= _MAX, "proxy_length_invalid")
                    remaining, data = int(length), bytearray()
                    deadline = time.monotonic() + 6
                    while remaining:
                        timeout = deadline - time.monotonic()
                        p.require(timeout > 0, "proxy_request_deadline")
                        self.connection.settimeout(timeout)
                        part = self.rfile.read1(min(remaining, 65536))
                        p.require(bool(part), "proxy_body_incomplete")
                        data.extend(part)
                        remaining -= len(part)
                    self.connection.settimeout(6)
                    response = owner.forward(method, self.path, bytes(data))
                    self.send_response(response.status_code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response.body)))
                    self.send_header("X-Elastic-Product", "Elasticsearch")
                    self.end_headers()
                    self.wfile.write(response.body)
                except Exception:
                    try:
                        self.send_error(502)
                    except OSError:
                        pass

        failed = False
        try:
            self.server = Server(("127.0.0.1", self.port), Handler)
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except Exception:
            failed = True
        if failed:
            self.violate()
            raise p.ProtocolError("proxy_start_failed") from None

    def close(self) -> None:
        with self._lock:
            p.require(not self._closing and not self.closed, "proxy_already_closed")
            self._closing = True
            connections = tuple(self._connections)
        failed = False
        try:
            if self.server is not None:
                if self.thread is not None and self.thread.is_alive():
                    self.server.shutdown()
                # Close only sockets accepted by this owned server, including
                # a client stalled before Content-Length/body processing.
                for connection in connections:
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass  # Already closed by its owned handler is harmless.
                    connection.close()
                self.server.server_close()
            if self.thread is not None and self.thread.ident is not None:
                self.thread.join(timeout=6)
                p.require(not self.thread.is_alive(), "proxy_thread_still_running")
            with self._lock:
                p.require(self._inflight == 0, "proxy_sends_pending")
                self._closed = True
        except Exception:
            failed = True
        if failed:
            raise p.ProtocolError("proxy_cleanup_failed") from None
