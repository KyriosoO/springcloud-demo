"""Private, bounded loopback helpers for Knowledge measurement startup validation.

This module never executes a UAT case. Its proxy makes Java's ES metadata and
search requests observable without exposing response bodies in evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any, cast

import httpx
import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse, KnowledgeHttpTransport
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import StructuredModelRequest, StructuredModelResponse, StructuredModelTransport
from tests.uat.knowledge_rebuild_measure_prepare import _ENV
from tests.uat.knowledge_rebuild_measure_budget import PLAN


_NAME = re.compile(r"[A-Za-z0-9._-]{1,256}\Z")
_MAX_BODY = 2 * 1024 * 1024
_MAX_RESPONSE = 8 * 1024 * 1024


class StartupError(ValueError):
    pass


class MeasureEsProxy:
    """Count bounded Java→ES requests; deny all writes and unknown routes."""

    def __init__(self, *, index_name: str, read_alias: str, port: int,
                 metadata_limit: int, search_limit: int, backend: httpx.Client) -> None:
        if (not _NAME.fullmatch(index_name) or not _NAME.fullmatch(read_alias)
                or type(port) is not int or not 1 <= port <= 65535
                or type(metadata_limit) is not int or not 1 <= metadata_limit <= PLAN.launcher_limits()["runtimeMetadataEsHttpMax"]
                or type(search_limit) is not int or not 0 <= search_limit <= PLAN.limits()["search"]
                or backend.base_url != httpx.URL("http://127.0.0.1:9200")
                or backend.follow_redirects or backend.trust_env):
            raise StartupError("knowledge.measure.proxy_binding_invalid")
        self.index_name = index_name
        self.read_alias = read_alias
        self.port = port
        self.metadata_limit = metadata_limit
        self.search_limit = search_limit
        self.backend = backend
        self.metadata_attempts = 0
        self.search_attempts = 0
        self.violations = 0
        self._metadata_paths: dict[str, int] = {}
        self._lock = Lock()
        self._server: ThreadingHTTPServer | None = None

    def _admit(self, method: str, path: str, length: int) -> bool:
        metadata = {"/_cluster/health", "/_cluster/health/", f"/_alias/{self.read_alias}",
                    f"/{self.index_name}/_settings", f"/{self.index_name}/_mapping",
                    f"/{self.index_name}"}
        with self._lock:
            if method == "GET" and path in metadata and length == 0:
                if self.metadata_attempts < self.metadata_limit:
                    self.metadata_attempts += 1
                    self._metadata_paths[path] = self._metadata_paths.get(path, 0) + 1
                    return True
            elif (method == "POST" and path == f"/{self.read_alias}/_search"
                  and 0 < length <= _MAX_BODY):
                if self.search_attempts < self.search_limit:
                    self.search_attempts += 1
                    return True
            self.violations += 1
            return False

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {"metadataEsHttp": self.metadata_attempts,
                    "searchEsHttp": self.search_attempts, "proxyViolations": self.violations,
                    "healthEsHttp": (self._metadata_paths.get("/_cluster/health", 0)
                                     + self._metadata_paths.get("/_cluster/health/", 0)),
                    "aliasEsHttp": self._metadata_paths.get(f"/_alias/{self.read_alias}", 0),
                    "settingsEsHttp": self._metadata_paths.get(f"/{self.index_name}/_settings", 0),
                    "mappingEsHttp": self._metadata_paths.get(f"/{self.index_name}/_mapping", 0),
                    "definitionEsHttp": self._metadata_paths.get(f"/{self.index_name}", 0)}

    def forward(self, method: str, path: str, body: bytes) -> tuple[int, str, bytes, str | None]:
        if not self._admit(method, path, len(body)):
            raise StartupError("knowledge.measure.proxy_request_forbidden")
        try:
            with self.backend.stream(method, path, content=body if method == "POST" else None,
                    headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
                    timeout=10.0, follow_redirects=False) as response:
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise StartupError("knowledge.measure.proxy_response_encoding_invalid")
                products = response.headers.get_list("x-elastic-product")
                product = products[0] if products else None
                if (len(products) > 1 or (product is not None and
                        (not 1 <= len(product) <= 64
                         or any(not 32 <= ord(char) <= 126 for char in product)))):
                    raise StartupError("knowledge.measure.proxy_response_product_header_invalid")
                bounded = bytearray()
                for part in response.iter_bytes():
                    if len(bounded) + len(part) > _MAX_RESPONSE:
                        raise StartupError("knowledge.measure.proxy_response_too_large")
                    bounded.extend(part)
                return (response.status_code, response.headers.get("content-type", "application/json"),
                        bytes(bounded), product)
        except Exception:
            with self._lock:
                self.violations += 1
            raise

    def serve(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                self._forward("GET")

            def do_POST(self) -> None:
                self._forward("POST")

            def do_PUT(self) -> None:
                self._forward("PUT")

            def do_DELETE(self) -> None:
                self._forward("DELETE")

            def _forward(self, method: str) -> None:
                if method == "GET" and self.path == "/__counts":
                    value = (json.dumps(owner.counts(), sort_keys=True, separators=(",", ":")) + "\n").encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(value)))
                    self.end_headers()
                    self.wfile.write(value)
                    return
                forwarded = False
                try:
                    raw_length = self.headers.get("Content-Length", "0")
                    if not raw_length.isascii() or not raw_length.isdecimal():
                        raise ValueError("length")
                    length = int(raw_length)
                    if length > _MAX_BODY:
                        raise ValueError("body")
                    body = self.rfile.read(length)
                    if len(body) != length:
                        raise ValueError("body")
                    forwarded = True
                    status, content_type, value, product = owner.forward(method, self.path, body)
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(value)))
                    if product is not None:
                        # Preserve the upstream identity; never invent a valid product marker.
                        self.send_header("X-Elastic-Product", product)
                    self.end_headers()
                    self.wfile.write(value)
                except Exception:
                    if not forwarded:
                        with owner._lock:
                            owner.violations += 1
                    self.send_error(502)

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        try:
            self._server.serve_forever()
        finally:
            self._server.server_close()


class _DenyModel(StructuredModelTransport):
    def __init__(self, violation_marker: Path) -> None:
        self.marker = violation_marker

    async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
        del request, call_deadline
        self.marker.touch(exist_ok=True)
        raise StartupError("knowledge.measure.startup_model_outbound_forbidden")


class _DenyKnowledge(KnowledgeHttpTransport):
    def __init__(self, violation_marker: Path) -> None:
        self.marker = violation_marker

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        del request, timeout_s
        self.marker.touch(exist_ok=True)
        raise StartupError("knowledge.measure.startup_knowledge_outbound_forbidden")


def runtime_app(*, startup_input: dict[str, Any], violation_marker: Path) -> Any:
    runtime_env = startup_input["runtimeEnv"]
    if type(runtime_env) is not dict or runtime_env != _ENV:
        raise StartupError("knowledge.measure.startup_runtime_env_invalid")
    # Never consult the process's real LLM_API_KEY. The synthetic value is only
    # for constructor validation; every model and retrieval send is rejected.
    environment = {**runtime_env, "LLM_API_KEY": "startup-synthetic-not-a-credential"}
    deny_model = _DenyModel(violation_marker)
    deny_knowledge = _DenyKnowledge(violation_marker)
    return create_app(RuntimeHttpSettings(host="127.0.0.1", port=19203, max_in_flight=1),
        lambda: build_runtime(environment, model_transport_wrapper=lambda delegate: deny_model,
            knowledge_transport_wrapper=lambda name, delegate: deny_knowledge))


def _load_startup_input(path: Path, expected_sha256: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if (len(raw) > 131072 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise StartupError("knowledge.measure.startup_input_invalid")
    value = json.loads(raw)
    expected_fields = {"schemaVersion", "status", "startupId", "sourceRunId", "branch", "head",
                       "buildAttestationPath", "buildAttestationSha256", "jarSha256",
                       "dependencyJarSha256", "configSha256", "assetSha256", "datasetSha256",
                       "indexBindings", "aliasFlags", "runtimeEnv", "subject",
                       "bindingMetadataEsHttp", "maximumStartupMetadataEsHttp",
                       "modelRequests", "typedSearchRequests", "embeddingRequests", "rerankRequests"}
    if (type(value) is not dict or set(value) != expected_fields
            or value.get("schemaVersion") != 1 or value.get("status") != "startup_input"
            or value.get("branch") != "codex_0915"
            or not isinstance(value.get("head"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", value["head"])
            or value.get("startupId") != path.resolve().parent.name
            or value.get("runtimeEnv") != _ENV
            or value.get("subject") != {"userId": "viewer_t", "role": "VIEWER"}
            or value.get("bindingMetadataEsHttp") != PLAN.startup_binding_reads
            or value.get("maximumStartupMetadataEsHttp") != PLAN.launcher_limits()["startupMetadataMax"]
            or value.get("modelRequests") != 0 or value.get("typedSearchRequests") != 0
            or value.get("embeddingRequests") != 0 or value.get("rerankRequests") != 0):
        raise StartupError("knowledge.measure.startup_input_invalid")
    return cast(dict[str, Any], value)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    proxy = commands.add_parser("proxy")
    proxy.add_argument("--index-name", required=True)
    proxy.add_argument("--read-alias", required=True)
    proxy.add_argument("--port", type=int, required=True)
    proxy.add_argument("--metadata-limit", type=int, required=True)
    proxy.add_argument("--search-limit", type=int, required=True)
    runtime = commands.add_parser("runtime")
    runtime.add_argument("--startup-input", type=Path, required=True)
    runtime.add_argument("--expected-sha256", required=True)
    runtime.add_argument("--violation-marker", type=Path, required=True)
    runtime.add_argument("--stop-marker", type=Path, required=True)
    runtime.add_argument("--closed-marker", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "proxy":
        with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                          trust_env=False, timeout=10.0) as backend:
            MeasureEsProxy(index_name=args.index_name, read_alias=args.read_alias, port=args.port,
                metadata_limit=args.metadata_limit, search_limit=args.search_limit,
                backend=backend).serve()
    else:
        startup_input = _load_startup_input(args.startup_input, args.expected_sha256)
        marker = args.violation_marker.resolve()
        stop_marker = args.stop_marker.resolve()
        closed_marker = args.closed_marker.resolve()
        parent = args.startup_input.resolve().parent
        if (any(path.exists() or path.parent != parent for path in (marker, stop_marker, closed_marker))
                or len({marker, stop_marker, closed_marker}) != 3):
            raise StartupError("knowledge.measure.startup_marker_invalid")
        app = runtime_app(startup_input=startup_input, violation_marker=marker)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19203,
                                              workers=1, access_log=False, log_level="warning"))

        async def serve_until_stop() -> None:
            async def stop_watcher() -> None:
                while not stop_marker.exists():
                    await asyncio.sleep(0.1)
                server.should_exit = True

            watcher = asyncio.create_task(stop_watcher())
            try:
                await server.serve()
                if marker.exists() or not stop_marker.exists():
                    raise StartupError("knowledge.measure.startup_runtime_not_clean")
                with closed_marker.open("xb") as stream:
                    stream.write(b"closed\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                watcher.cancel()
                try:
                    await watcher
                except asyncio.CancelledError:
                    pass

        asyncio.run(serve_until_stop())


if __name__ == "__main__":
    main()
