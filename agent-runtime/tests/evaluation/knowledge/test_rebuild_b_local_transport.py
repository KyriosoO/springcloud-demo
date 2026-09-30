"""No-socket tests for B physical-path witness and one-use alias lease."""
from __future__ import annotations

from hashlib import sha256
import json
import socket

import httpx
import pytest

from tests.evaluation.knowledge.rebuild_b_local_transport import (
    ArmIdentity, BIsolatedAliases, BLocalTransportError, PhysicalEsProxy, _canonical,
    _request_hashes,
)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


class FakeEs:
    def __init__(self) -> None:
        self.mapping = {"_meta": {"mapping_version": "map-v1"}, "properties": {}}
        self.names = ("frozen-source", "frozen-candidate", "online-old")
        self.aliases: dict[str, dict[str, dict[str, object]]] = {
            name: {} for name in self.names
        }
        self.aliases["online-old"]["knowledge-read"] = {}
        self.operations: list[tuple[str, str]] = []
        self.drift_on_next_alias_read = False
        self.omit_alias_errors = False

    def identity(self, arm: str, index: str, suffix: str) -> ArmIdentity:
        return ArmIdentity(arm, index, index + "-uuid", _hash(self.mapping),
                           "map-v1", f"b-local-run-{suffix}-read")

    def online_alias_raw(self) -> dict[str, object]:
        return {"online-old": {"aliases": {"knowledge-read": {}}}}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.operations.append((method, path))
        if method == "GET" and path.startswith("/_alias/"):
            alias = path.removeprefix("/_alias/")
            matches = {index: {"aliases": {alias: definitions[alias]}}
                       for index, definitions in self.aliases.items() if alias in definitions}
            if self.drift_on_next_alias_read and alias != "knowledge-read" and matches:
                self.drift_on_next_alias_read = False
                first = next(iter(matches.values()))
                first["aliases"][alias]["filter"] = {"term": {"channel": "unknown"}}
            return httpx.Response(200 if matches else 404, json=matches)
        if method == "GET" and path.removeprefix("/") in self.names:
            name = path.removeprefix("/")
            return httpx.Response(200, json={name: {
                "settings": {"index": {"uuid": name + "-uuid", "blocks": {"write": "true"}}},
                "mappings": self.mapping, "aliases": self.aliases[name],
            }})
        if method == "POST" and path == "/_aliases":
            payload = json.loads(request.content)
            for action in payload["actions"]:
                if "add" in action:
                    item = action["add"]
                    self.aliases[item["index"]][item["alias"]] = {
                        "is_hidden": item["is_hidden"], "is_write_index": item["is_write_index"],
                    }
                elif "remove" in action:
                    item = action["remove"]
                    self.aliases[item["index"]].pop(item["alias"], None)
                else:
                    return httpx.Response(400)
            result: dict[str, object] = {"acknowledged": True}
            if not self.omit_alias_errors:
                result["errors"] = False
            return httpx.Response(200, json=result)
        return httpx.Response(400)


def _lease(fake: FakeEs) -> tuple[BIsolatedAliases, httpx.Client]:
    client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                          follow_redirects=False, transport=httpx.MockTransport(fake))
    baseline = fake.identity("baseline", "frozen-source", "a" * 16)
    candidate = fake.identity("candidate", "frozen-candidate", "b" * 16)
    lease = BIsolatedAliases(client=client, baseline=baseline, candidate=candidate,
        online_alias="knowledge-read", online_index="online-old", online_uuid="online-old-uuid",
        online_mapping_sha256=_hash(fake.mapping),
        online_alias_sha256=_hash(fake.online_alias_raw()), mapping_fingerprint=_hash)
    return lease, client


def test_alias_lease_exact_success_and_30_call_total_with_java_startup() -> None:
    fake = FakeEs()
    lease, client = _lease(fake)
    try:
        pre = lease.open()
        assert len(pre) == 2
        assert lease.postcheck() == pre
        assert lease.close()
        assert lease.alias_writes == 4
        assert lease.metadata_calls == 18  # Java's 12 verifier GETs use two proxies.
        assert all(not fake.aliases[name] for name in fake.names[:2])
        assert not any(path.endswith("/_search") for _, path in fake.operations)
    finally:
        client.close()


def test_alias_lease_accepts_official_ack_without_optional_errors() -> None:
    fake = FakeEs()
    fake.omit_alias_errors = True
    lease, client = _lease(fake)
    try:
        assert len(lease.open()) == 2
        lease.postcheck()
        assert lease.close()
        assert lease.alias_writes == 4
    finally:
        client.close()


def test_alias_lease_rejects_partial_or_unknown_error_result() -> None:
    assert not BIsolatedAliases._acknowledged({"acknowledged": True, "errors": True,
                                              "action_results": [{"status": 404}]})
    assert not BIsolatedAliases._acknowledged({"acknowledged": True,
                                              "action_results": [{"status": 200}]})
    assert not BIsolatedAliases._acknowledged({"acknowledged": True, "error": {"type": "x"}})


def test_alias_lease_refuses_online_drift_before_any_write() -> None:
    fake = FakeEs()
    lease, client = _lease(fake)
    fake.aliases["online-old"]["knowledge-read"] = {"filter": {"match_all": {}}}
    try:
        with pytest.raises(BLocalTransportError, match="online_binding_drift"):
            lease.open()
        assert lease.alias_writes == 0
    finally:
        client.close()


def test_alias_lease_does_not_remove_mutated_or_foreign_alias() -> None:
    fake = FakeEs()
    lease, client = _lease(fake)
    try:
        lease.open()
        lease.postcheck()
        fake.drift_on_next_alias_read = True
        assert not lease.close()
        assert lease.alias_writes < 4
        assert any(fake.aliases[name] for name in fake.names[:2])
    finally:
        client.close()


def test_proxy_rejects_unknown_target_and_counts_failed_attempts() -> None:
    fake = FakeEs()
    client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                          follow_redirects=False, transport=httpx.MockTransport(fake))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
                             port=19310, maximum_metadata=6, maximum_search=2, backend=client)
    try:
        assert not proxy._admit("POST", "/knowledge-read/_search", 25)
        assert not proxy._admit("PUT", "/frozen-source/_doc/x", 25)
        assert proxy._admit("POST", "/frozen-source/_search", 25)
        assert proxy._admit("POST", "/frozen-source/_search", 25)
        assert not proxy._admit("POST", "/frozen-source/_search", 25)
        assert proxy._admit("GET", "/_alias/b-local-run-" + "a" * 16 + "-read", 0)
        assert not proxy._admit("GET", "/_alias/b-local-run-" + "a" * 16 + "-read?x=1", 0)
        assert proxy.violations == 4
        assert not fake.operations
    finally:
        client.close()


def test_startup_proxy_zero_search_budget_never_forwards_search() -> None:
    fake = FakeEs()
    client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                          follow_redirects=False, transport=httpx.MockTransport(fake))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
                             port=19310, maximum_metadata=6, maximum_search=0, backend=client)
    try:
        assert not proxy._admit("POST", "/frozen-source/_search", 25)
        assert proxy.violations == 1
        assert proxy.physical_search_paths == ()
        assert fake.operations == []
        assert proxy._admit("GET", "/frozen-source/_mapping", 0)
    finally:
        client.close()


def test_startup_proxy_http_search_is_denied_before_backend() -> None:
    fake = FakeEs()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
        follow_redirects=False,
        transport=httpx.MockTransport(lambda _request: pytest.fail("backend called")))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
                             port=port, maximum_metadata=6, maximum_search=0, backend=backend)
    try:
        proxy.start()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            response = client.post(f"http://127.0.0.1:{port}/frozen-source/_search", json={})
        assert response.status_code == 502
        assert proxy.violations > 0
        assert proxy.physical_search_paths == ()
        assert proxy.metadata_attempts == 0
    finally:
        proxy.close()
        backend.close()


def test_proxy_stream_refuses_oversized_fake_es_response_without_body_evidence() -> None:
    fake = FakeEs()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
        follow_redirects=False, transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"x" * (8 * 1024 * 1024 + 1))))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
                             port=port, maximum_metadata=6, maximum_search=2, backend=backend)
    try:
        proxy.start()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            response = client.get(f"http://127.0.0.1:{port}/frozen-source/_mapping")
        assert response.status_code == 502
        assert proxy.violations == 1
        assert proxy.requests == []
        assert proxy.metadata_attempts == 1
        assert proxy.metadata_count == 0
    finally:
        proxy.close()
        backend.close()


def test_request_hashes_preserve_raw_but_ignore_only_object_key_order_and_whitespace() -> None:
    left = b'{ "b": {"z": 2, "a": [1, 1.0]}, "a": "value" }'
    right = b'{"a":"value","b":{"a":[1,1.0],"z":2}}'
    assert _request_hashes("POST", left)[0] != _request_hashes("POST", right)[0]
    assert _request_hashes("POST", left)[1] == _request_hashes("POST", right)[1]
    baseline = _request_hashes("POST", b'{"items":[1,2],"value":1}')
    for changed in (b'{"items":[2,1],"value":1}',
                    b'{"items":[1,2],"value":1.0}',
                    b'{"items":[1,2],"value":2}',
                    b'{"items":[1,2],"value":"1"}'):
        assert _request_hashes("POST", changed)[1] != baseline[1]
    assert (_request_hashes("POST", b'{"value":1.0000000000000001}')[1]
            != _request_hashes("POST", b'{"value":1.0}')[1])
    assert (_request_hashes("POST", b'{"value":1e-999}')[1]
            != _request_hashes("POST", b'{"value":0.0}')[1])
    empty_sha256 = sha256(b"").hexdigest()
    assert _request_hashes("GET", b"") == (empty_sha256, empty_sha256)
    with pytest.raises(BLocalTransportError, match="request_invalid"):
        _request_hashes("GET", b"x")


@pytest.mark.parametrize("invalid", (
    b'{"outer":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":1e309}', b'{"nested":{"x":1e309}}', b'[1,2]', b'{"x":',
    b'{"x":"\xff"}',
))
def test_invalid_search_json_never_reaches_backend(invalid: bytes) -> None:
    fake = FakeEs()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    forwarded: list[bytes] = []

    def backend_request(request: httpx.Request) -> httpx.Response:
        forwarded.append(request.content)
        return httpx.Response(200, json={})

    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
        follow_redirects=False, transport=httpx.MockTransport(backend_request))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
        port=port, maximum_metadata=6, maximum_search=2, backend=backend)
    try:
        proxy.start()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            response = client.post(f"http://127.0.0.1:{port}/frozen-source/_search",
                content=invalid)
        assert response.status_code == 502
        assert forwarded == []
        assert proxy.requests == []
        assert proxy.physical_search_paths == ()
        assert proxy.violations == 1
    finally:
        proxy.close()
        backend.close()


def test_proxy_forwards_original_search_bytes_and_records_both_hashes() -> None:
    fake = FakeEs()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    forwarded: list[bytes] = []

    def backend_request(request: httpx.Request) -> httpx.Response:
        forwarded.append(request.content)
        return httpx.Response(200, json={})

    backend = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
        follow_redirects=False, transport=httpx.MockTransport(backend_request))
    proxy = PhysicalEsProxy(identity=fake.identity("baseline", "frozen-source", "a" * 16),
        port=port, maximum_metadata=6, maximum_search=2, backend=backend)
    body = b'{ "b":2, "a":1 }'
    try:
        proxy.start()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            search = client.post(f"http://127.0.0.1:{port}/frozen-source/_search", content=body)
            metadata = client.get(f"http://127.0.0.1:{port}/frozen-source/_mapping")
        assert search.status_code == metadata.status_code == 200
        assert forwarded[0] == body
        assert proxy.requests[0].request_sha256 == sha256(body).hexdigest()
        assert proxy.requests[0].canonical_request_sha256 == _request_hashes("POST", body)[1]
        empty_sha256 = sha256(b"").hexdigest()
        assert proxy.requests[1].request_sha256 == empty_sha256
        assert proxy.requests[1].canonical_request_sha256 == empty_sha256
    finally:
        proxy.close()
        backend.close()
