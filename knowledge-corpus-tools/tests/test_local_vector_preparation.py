from __future__ import annotations

import copy
import json
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.local_vector_preparation import (
    MODEL_FILES, SERVICE_SHA, LocalVectorPreparation, PreparationError, _PROBE, _TOKENS,
)
from knowledge_corpus_tools.vector_representation import build_vector_representation

CONTAINER = "a" * 64
TEXT = "仅在本地处理的测试正文"
ITEM = build_vector_representation(content=TEXT)


class FakeLocal:
    def __init__(self) -> None:
        self.identity: dict[str, Any] = {
            "id": CONTAINER, "image": "sha256:" + "b" * 64,
            "started": "2026-09-07T00:48:23.858361985Z", "running": True, "path": "python",
            "args": ["-m", "uvicorn", "embedding_server:app", "--host", "0.0.0.0", "--port", "8908"],
            "ports": {"8908/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8908"}]},
        }
        digest = {"bytes": 1, "sha256": "c" * 64}
        self.model: dict[str, Any] = {
            "revision": "d" * 40, "max_length": 1024,
            "cache_provenance": "single_snapshot_predates_start",
            "service": {"bytes": 123, "sha256": SERVICE_SHA}, "implementation": digest.copy(),
            "files": {name: digest.copy() for name in MODEL_FILES},
            "packages": {"FlagEmbedding": "1.4.0", "transformers": "5.9.0", "torch": "2.6.0+cu124"},
        }
        self.processes: list[tuple[list[str], bytes]] = []
        self.requests: list[httpx.Request] = []
        self.count: Any = 16
        self.mode = "normal"
        self.snapshot_calls = 0
        self.prep = LocalVectorPreparation(CONTAINER, process=self.process,
                                           transport=httpx.MockTransport(self.http))

    def process(self, command: list[str], payload: bytes) -> bytes:
        self.processes.append((command, payload))
        if command[1] == "inspect":
            self.snapshot_calls += 1
            value = copy.deepcopy(self.identity)
            if self.mode == "changed" and self.snapshot_calls > 1:
                value["image"] = "sha256:" + "e" * 64
            if self.mode == "changed_after" and self.snapshot_calls > 2:
                value["image"] = "sha256:" + "e" * 64
        elif command[-1] == _PROBE:
            assert "texts" not in json.loads(payload)
            value = self.model
        else:
            assert command[-1] == _TOKENS
            texts = json.loads(payload)["texts"]
            value = [self.count] * len(texts)
        return json.dumps(value).encode()

    def http(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert str(request.url) == "http://127.0.0.1:8908/embed"
        texts = json.loads(request.content)["texts"]
        assert all(t == TEXT for t in texts) and 1 <= len(texts) <= 32
        if self.mode == "timeout":
            raise httpx.ReadTimeout(TEXT, request=request)
        if self.mode == "redirect":
            return httpx.Response(307, headers={"location": "https://example.com"})
        if self.mode == "raw_invalid":
            return httpx.Response(200, content=TEXT)
        if self.mode == "duplicate":
            return httpx.Response(200, content=b'{"dim":1024,"dim":1024,"vectors":[]}')
        if self.mode == "oversized":
            return httpx.Response(200, content=b" " * (2 * 1024 * 1024 + 1))
        vector: list[Any] = [0.125] * 1024
        if self.mode == "bool_vector":
            vector[0] = True
        if self.mode == "zero_vector":
            vector = [0] * 1024
        if self.mode == "float_overflow":
            vector[0] = 1e300
        if self.mode == "short_vector":
            vector.pop()
        return httpx.Response(200, json={"dim": 1024, "vectors": [vector] * len(texts)})


def test_all_token_checks_precede_embedding_and_batches_are_bounded() -> None:
    fake = FakeLocal()
    snapshot = fake.prep.freeze()
    assert len(fake.prep.snapshot_sha256) == 64
    snapshot["model"]["revision"] = "untrusted_mutation"
    vectors = fake.prep((ITEM,) * 65)
    assert len(vectors) == 65 and all(type(v) is tuple for v in vectors)
    assert fake.prep.http_calls == 3 and fake.prep.text_count == 65
    assert fake.prep.max_tokens == 16 and fake.snapshot_calls == 3
    assert len([p for p in fake.processes if p[0][-1] == _TOKENS]) == 1
    with pytest.raises(PreparationError, match="already_consumed"):
        fake.prep((ITEM,))
    assert len(fake.requests) == 3


@pytest.mark.parametrize("count", [1025, True, 0, "16", None, -1])
def test_bad_or_excess_tokens_have_zero_embedding(count: Any) -> None:
    fake = FakeLocal()
    fake.count = count
    fake.prep.freeze()
    with pytest.raises(PreparationError):
        fake.prep((ITEM,))
    assert not fake.requests


@pytest.mark.parametrize("mode", ["timeout", "redirect", "raw_invalid", "duplicate", "oversized",
                                  "bool_vector", "zero_vector", "float_overflow", "short_vector"])
def test_model_failures_are_finite_without_retry_or_raw_exception_context(mode: str) -> None:
    fake = FakeLocal()
    fake.mode = mode
    fake.prep.freeze()
    with pytest.raises(PreparationError) as caught:
        fake.prep((ITEM,))
    assert len(fake.requests) == 1
    assert TEXT not in str(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("mode,expected_calls", [("changed", 0), ("changed_after", 1)])
def test_model_identity_change_blocks_prepared_vector_return(mode: str, expected_calls: int) -> None:
    fake = FakeLocal()
    fake.mode = mode
    fake.prep.freeze()
    with pytest.raises(PreparationError, match="identity_changed"):
        fake.prep((ITEM,))
    assert len(fake.requests) == expected_calls


@pytest.mark.parametrize("field,value", [("service", {"bytes": 1, "sha256": "f" * 64}),
                                         ("max_length", 8192), ("files", {}),
                                         ("revision", "../../escape"), ("packages", {})])
def test_unverified_model_identity_is_not_frozen(field: str, value: Any) -> None:
    fake = FakeLocal()
    fake.model[field] = value
    with pytest.raises(PreparationError):
        fake.prep.freeze()
    assert not fake.requests


@pytest.mark.parametrize("field,value", [("running", False), ("id", "b" * 64),
                                         ("args", []), ("ports", {}), ("image", "unbound")])
def test_unverified_container_rejected(field: str, value: Any) -> None:
    fake = FakeLocal()
    fake.identity[field] = value
    with pytest.raises(PreparationError):
        fake.prep.freeze()


def test_no_prepare_without_freeze_or_over_limit() -> None:
    fake = FakeLocal()
    with pytest.raises(PreparationError, match="already_consumed"):
        fake.prep((ITEM,))
    fake.prep.freeze()
    with pytest.raises(PreparationError, match="input_invalid"):
        fake.prep((ITEM,) * 1001)
    assert not fake.requests


def test_programs_do_not_load_embedding_model_or_truncate_tokens() -> None:
    assert "import embedding_server" not in _PROBE + _TOKENS
    assert "truncation=False" in _TOKENS and "local_files_only=True" in _TOKENS
    assert "trust_remote_code=False" in _TOKENS and "add_special_tokens=True" in _TOKENS
    assert 'path.open("rb")' in _PROBE
    assert 'assert {p.name for p in (root / "snapshots").iterdir()} == {revision}' in _PROBE
    assert 'assert snapshot.stat().st_mtime < started' in _PROBE
