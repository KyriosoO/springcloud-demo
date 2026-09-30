"""Local-only ES identity and physical-request witness for one B comparison.

The proxy deliberately does not parse, log or persist request/response bodies. It
exists only to prove which physical ES path the two owned Java processes used.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from threading import Lock, Thread
from typing import Any, Callable

import httpx


_INDEX = re.compile(r"[A-Za-z0-9._-]{1,256}\Z")
_ALIAS = re.compile(r"b-[a-z0-9-]{5,96}-[0-9a-f]{16,32}-read\Z")
_MAX_BODY = 2 * 1024 * 1024
_MAX_RESPONSE = 8 * 1024 * 1024


class BLocalTransportError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _object(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > _MAX_RESPONSE:
        raise BLocalTransportError("metadata_invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError):
        raise BLocalTransportError("metadata_invalid") from None
    if type(value) is not dict:
        raise BLocalTransportError("metadata_invalid")
    return value


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate_key")
        result[name] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("non_finite")


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class ArmIdentity:
    arm: str
    index_name: str
    index_uuid: str
    mapping_sha256: str
    mapping_version: str
    alias: str

    def __post_init__(self) -> None:
        if (self.arm not in ("baseline", "candidate")
                or type(self.index_name) is not str or _INDEX.fullmatch(self.index_name) is None
                or type(self.index_uuid) is not str or _INDEX.fullmatch(self.index_uuid) is None
                or type(self.mapping_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.mapping_sha256) is None
                or type(self.mapping_version) is not str or not self.mapping_version
                or type(self.alias) is not str or _ALIAS.fullmatch(self.alias) is None):
            raise BLocalTransportError("identity_invalid")


def check_index_definition(value: dict[str, Any], identity: ArmIdentity,
                           *, mapping_fingerprint: Callable[[dict[str, Any]], str]) -> None:
    """Accept one exact physical index identity, not a matching alias name."""
    if set(value) != {identity.index_name}:
        raise BLocalTransportError("index_drift")
    try:
        index = value[identity.index_name]
        settings = index["settings"]["index"]
        mapping = index["mappings"]
        if (settings["uuid"] != identity.index_uuid
                or mapping["_meta"]["mapping_version"] != identity.mapping_version
                or mapping_fingerprint(mapping) != identity.mapping_sha256):
            raise BLocalTransportError("index_drift")
    except (KeyError, TypeError, ValueError):
        raise BLocalTransportError("index_drift") from None


def check_isolated_alias(value: dict[str, Any], identity: ArmIdentity) -> None:
    """Reject filter, routing, implicit flags and any second physical target."""
    if set(value) != {identity.index_name}:
        raise BLocalTransportError("alias_drift")
    try:
        aliases = value[identity.index_name]["aliases"]
        flags = aliases[identity.alias]
        if (set(aliases) != {identity.alias}
                or flags != {"is_hidden": True, "is_write_index": False}):
            raise BLocalTransportError("alias_drift")
    except (KeyError, TypeError):
        raise BLocalTransportError("alias_drift") from None


@dataclass(frozen=True, slots=True)
class RequestWitness:
    method: str
    path: str
    request_sha256: str
    status: int


class PhysicalEsProxy:
    """Owned loopback forwarder; only startup metadata and fixed search are possible."""

    def __init__(self, *, identity: ArmIdentity, port: int, maximum_metadata: int,
                 maximum_search: int, backend: httpx.Client) -> None:
        if (type(port) is not int or not 1 <= port <= 65535
                or type(maximum_metadata) is not int or not 1 <= maximum_metadata <= 512
                or type(maximum_search) is not int or not 1 <= maximum_search <= 48
                or backend.base_url.scheme != "http" or backend.base_url.host != "127.0.0.1"
                or backend.base_url.port != 9200 or backend.follow_redirects or backend.trust_env):
            raise BLocalTransportError("proxy_binding_invalid")
        self.identity = identity
        self.port = port
        self.maximum_metadata = maximum_metadata
        self.maximum_search = maximum_search
        self.backend = backend
        self.requests: list[RequestWitness] = []
        self.violations = 0
        self._lock = Lock()
        self._search_attempts = 0
        self._metadata_attempts = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def _admit(self, method: str, path: str, size: int) -> bool:
        with self._lock:
            metadata = {
                ("GET", f"/_alias/{self.identity.alias}"),
                ("GET", f"/{self.identity.index_name}/_settings"),
                ("GET", f"/{self.identity.index_name}/_mapping"),
            }
            if method == "POST" and path == f"/{self.identity.index_name}/_search":
                allowed = 0 < size <= _MAX_BODY and self._search_attempts < self.maximum_search
                if allowed:
                    self._search_attempts += 1
            else:
                allowed = ((method, path) in metadata and size == 0
                           and self._metadata_attempts < self.maximum_metadata)
                if allowed:
                    self._metadata_attempts += 1
            if not allowed:
                self.violations += 1
            return allowed

    def start(self) -> None:
        if self._server is not None:
            raise BLocalTransportError("proxy_already_started")
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
                path = self.path
                try:
                    length_raw = self.headers.get("Content-Length", "0")
                    if not length_raw.isascii() or not length_raw.isdecimal():
                        raise ValueError("length")
                    length = int(length_raw)
                    if not owner._admit(method, path, length):
                        raise ValueError("path")
                    body = self.rfile.read(length)
                    if len(body) != length:
                        raise ValueError("body")
                    with owner.backend.stream(method, path, content=body if method == "POST" else None,
                            headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
                            timeout=10.0, follow_redirects=False) as response:
                        if response.headers.get("content-encoding", "identity") != "identity":
                            raise ValueError("response")
                        bounded = bytearray()
                        for part in response.iter_bytes():
                            if len(bounded) + len(part) > _MAX_RESPONSE:
                                raise ValueError("response")
                            bounded.extend(part)
                        raw = bytes(bounded)
                        with owner._lock:
                            owner.requests.append(RequestWitness(method, path, sha256(body).hexdigest(),
                                                                 response.status_code))
                        self.send_response(response.status_code)
                        self.send_header("Content-Type", response.headers.get("content-type", "application/json"))
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                except Exception:
                    with owner._lock:
                        owner.violations += 1
                    self.send_error(502)

        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError:
            raise BLocalTransportError("proxy_port_unavailable") from None
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            assert self._thread is not None
            self._thread.join(timeout=5)
            self._server = None
            self._thread = None

    @property
    def physical_search_paths(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(item.path for item in self.requests if item.method == "POST")

    @property
    def metadata_count(self) -> int:
        with self._lock:
            return sum(item.method == "GET" for item in self.requests)

    @property
    def metadata_attempts(self) -> int:
        with self._lock:
            return self._metadata_attempts


class BIsolatedAliases:
    """One-use two-arm alias lease with exact owner checks and finite ES budget.

    The two aliases are never moved between physical indices. A failed or
    ambiguous write is not retried; cleanup only removes an alias whose current
    definition still proves our ownership.
    """

    def __init__(self, *, client: httpx.Client, baseline: ArmIdentity,
                 candidate: ArmIdentity, online_alias: str, online_index: str,
                 online_uuid: str, online_mapping_sha256: str,
                 online_alias_sha256: str, mapping_fingerprint: Callable[[dict[str, Any]], str],
                 metadata_budget: int = 30, alias_write_budget: int = 4) -> None:
        if (client.base_url.scheme != "http" or client.base_url.host != "127.0.0.1"
                or client.base_url.port != 9200 or client.follow_redirects or client.trust_env
                or baseline.arm != "baseline" or candidate.arm != "candidate"
                or baseline.alias == candidate.alias or baseline.index_name == candidate.index_name
                or online_alias in (baseline.alias, candidate.alias)
                or type(online_alias) is not str or _INDEX.fullmatch(online_alias) is None
                or type(online_index) is not str or _INDEX.fullmatch(online_index) is None
                or type(online_uuid) is not str or _INDEX.fullmatch(online_uuid) is None
                or type(online_mapping_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", online_mapping_sha256) is None
                or type(online_alias_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", online_alias_sha256) is None
                or metadata_budget != 30 or alias_write_budget != 4):
            raise BLocalTransportError("alias_binding_invalid")
        self.client = client
        self.identities = (baseline, candidate)
        self.online_alias = online_alias
        self.online_index = online_index
        self.online_uuid = online_uuid
        self.online_mapping_sha256 = online_mapping_sha256
        self.online_alias_sha256 = online_alias_sha256
        self.mapping_fingerprint = mapping_fingerprint
        self.metadata_budget = metadata_budget
        self.alias_write_budget = alias_write_budget
        self.metadata_calls = 0
        self.alias_writes = 0
        self._created: set[str] = set()
        self._attempted: set[str] = set()
        self._pre_snapshots: tuple[tuple[str, str], ...] | None = None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None,
                 *, absent_ok: bool = False) -> dict[str, Any] | None:
        if method == "GET":
            if self.metadata_calls >= self.metadata_budget:
                raise BLocalTransportError("metadata_budget_exhausted")
            self.metadata_calls += 1
        elif method == "POST" and path == "/_aliases":
            if self.alias_writes >= self.alias_write_budget:
                raise BLocalTransportError("alias_budget_exhausted")
            self.alias_writes += 1
        else:
            raise BLocalTransportError("es_operation_forbidden")
        try:
            with self.client.stream(method, path, content=None if payload is None else _canonical(payload),
                    headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
                    timeout=10.0, follow_redirects=False) as response:
                if (response.headers.get("content-encoding", "identity") != "identity"
                        or response.status_code not in ((200, 404) if absent_ok else (200,))):
                    raise BLocalTransportError("es_response_invalid")
                body = bytearray()
                for part in response.iter_bytes():
                    if len(body) + len(part) > _MAX_RESPONSE:
                        raise BLocalTransportError("es_response_invalid")
                    body.extend(part)
                return None if response.status_code == 404 else _object(bytes(body))
        except BLocalTransportError:
            raise
        except Exception:
            raise BLocalTransportError("es_response_invalid") from None

    def _online(self) -> None:
        alias = self._request("GET", f"/_alias/{self.online_alias}")
        definition = self._request("GET", f"/{self.online_index}")
        try:
            valid = (alias is not None and definition is not None
                and set(alias) == {self.online_index}
                and sha256(_canonical(alias)).hexdigest() == self.online_alias_sha256
                and set(definition) == {self.online_index}
                and definition[self.online_index]["settings"]["index"]["uuid"] == self.online_uuid
                and definition[self.online_index]["settings"]["index"].get("blocks", {}).get("write")
                    in (True, "true")
                and self.mapping_fingerprint(definition[self.online_index]["mappings"])
                    == self.online_mapping_sha256)
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise BLocalTransportError("online_binding_drift")

    def _definition(self, identity: ArmIdentity) -> dict[str, Any]:
        raw = self._request("GET", f"/{identity.index_name}")
        if raw is None:
            raise BLocalTransportError("index_drift")
        check_index_definition(raw, identity, mapping_fingerprint=self.mapping_fingerprint)
        try:
            settings = raw[identity.index_name]["settings"]["index"]
            blocked = settings.get("blocks", {}).get("write") in (True, "true")
        except (KeyError, TypeError, AttributeError):
            blocked = False
        if not blocked:
            raise BLocalTransportError("index_not_read_only")
        return raw

    def _alias(self, identity: ArmIdentity, *, absent_ok: bool = False) -> dict[str, Any] | None:
        raw = self._request("GET", f"/_alias/{identity.alias}", absent_ok=absent_ok)
        if raw is None:
            if absent_ok:
                return None
            raise BLocalTransportError("alias_drift")
        check_isolated_alias(raw, identity)
        return raw

    def precheck(self) -> None:
        for identity in self.identities:
            self._definition(identity)
            if self._alias(identity, absent_ok=True) is not None:
                raise BLocalTransportError("alias_already_exists")
        self._online()

    def open(self) -> tuple[tuple[str, str], ...]:
        if self._created or self._pre_snapshots is not None:
            raise BLocalTransportError("alias_already_opened")
        self.precheck()
        for identity in self.identities:
            self._attempted.add(identity.alias)
            response = self._request("POST", "/_aliases", {"actions": [{"add": {
                "index": identity.index_name, "alias": identity.alias,
                "is_hidden": True, "is_write_index": False}}]})
            if not self._acknowledged(response):
                raise BLocalTransportError("alias_write_uncertain")
            self._created.add(identity.alias)
        snapshots: list[tuple[str, str]] = []
        for identity in self.identities:
            alias = self._alias(identity)
            assert alias is not None
            snapshots.append((identity.arm, sha256(_canonical({
                "index": identity.index_name, "uuid": identity.index_uuid,
                "mappingSha256": identity.mapping_sha256, "alias": alias,
                "onlineAliasSha256": self.online_alias_sha256,
            })).hexdigest()))
        self._pre_snapshots = tuple(snapshots)
        return self._pre_snapshots

    def postcheck(self) -> tuple[tuple[str, str], ...]:
        if self._pre_snapshots is None:
            raise BLocalTransportError("alias_not_opened")
        snapshots: list[tuple[str, str]] = []
        for identity in self.identities:
            self._definition(identity)
            alias = self._alias(identity)
            assert alias is not None
            snapshots.append((identity.arm, sha256(_canonical({
                "index": identity.index_name, "uuid": identity.index_uuid,
                "mappingSha256": identity.mapping_sha256, "alias": alias,
                "onlineAliasSha256": self.online_alias_sha256,
            })).hexdigest()))
        self._online()
        post = tuple(snapshots)
        if post != self._pre_snapshots:
            raise BLocalTransportError("postflight_drift")
        return post

    @staticmethod
    def _acknowledged(response: dict[str, Any] | None) -> bool:
        return (response is not None and response.get("acknowledged") is True
                and ("errors" not in response or response["errors"] is False)
                and "action_results" not in response and "error" not in response)

    def close(self) -> bool:
        """Never remove an alias unless its exact current owner is still proven."""
        clean = True
        for identity in reversed(self.identities):
            if identity.alias not in self._attempted:
                continue
            try:
                # A 404 proves an uncertain add created nothing. An exact match
                # is mandatory immediately before a one-target remove.
                if self._alias(identity, absent_ok=True) is None:
                    self._created.discard(identity.alias)
                    self._attempted.discard(identity.alias)
                    continue
                response = self._request("POST", "/_aliases", {"actions": [{"remove": {
                    "index": identity.index_name, "alias": identity.alias}}]})
                if not self._acknowledged(response):
                    clean = False
                    continue
                self._created.discard(identity.alias)
                self._attempted.discard(identity.alias)
            except BLocalTransportError:
                clean = False
        if clean:
            for identity in self.identities:
                if self._alias(identity, absent_ok=True) is not None:
                    clean = False
        return clean and not self._created
