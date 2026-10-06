"""No-Docker, no-inference checks for the B local model snapshot worker."""

from __future__ import annotations

import json
from hashlib import sha256
from importlib import metadata
from io import BytesIO
import sys
from typing import Any

import pytest

from knowledge_corpus_tools import b_model_identity_v1 as identity
from knowledge_corpus_tools.vector_candidate import canonical_bytes


_EMBED = "a" * 64
_RERANK = "b" * 64


def _fake_process(*, bad_port: bool = False,
                  bad_weight: bool = False) -> tuple[Any, list[list[str]]]:
    calls: list[list[str]] = []

    def invoke(command: list[str], payload: bytes) -> bytes:
        calls.append(command)
        assert command[0] == "docker"
        assert command[-1] == _RERANK if command[1] == "inspect" else command[3] == _RERANK
        if command[1] == "inspect":
            return json.dumps({
                "id": _RERANK, "image": "sha256:" + "c" * 64,
                "started": "2026-09-30T08:00:00Z", "running": True,
                "path": "python", "args": ["-m", "uvicorn", "reranker_server:app"],
                "ports": {"8909/tcp": [{"HostIp": "127.0.0.1",
                                          "HostPort": "8910" if bad_port else "8909"}]},
            }).encode()
        assert command[1:3] == ["exec", "-i"]
        program = command[-1]
        assert 'pathlib.Path("/app/reranker_server.py")' in program
        assert all(marker not in program for marker in (
            "from_pretrained", "AutoModel", "httpx", "requests", ".predict("))
        assert json.loads(payload)["revision"] == identity._REVISION
        files = dict(identity._RERANK_HASHES)
        if bad_weight:
            files["model.safetensors"] = "0" * 64
        return json.dumps({"revision": identity._REVISION, "files": files,
                           "serviceSha256": "d" * 64,
                           "packages": {"FlagEmbedding": "1.3.3",
                                        "transformers": "4.52.0",
                                        "torch": "2.5.0"}}).encode()

    return invoke, calls


def test_rerank_snapshot_is_read_only_and_exact() -> None:
    process, calls = _fake_process()
    snapshot = identity._rerank_snapshot(_RERANK, process)
    assert snapshot["model"]["files"] == identity._RERANK_HASHES
    assert "args" not in snapshot["container"] and len(snapshot["container"]["argsSha256"]) == 64
    assert [call[1] for call in calls] == ["inspect", "exec"]
    assert all(call[0] == "docker" for call in calls)


@pytest.mark.parametrize("fault", ["port", "weight"])
def test_rerank_snapshot_fails_closed(fault: str) -> None:
    process, _ = _fake_process(bad_port=fault == "port",
                               bad_weight=fault == "weight")
    with pytest.raises(identity.BModelIdentityError):
        identity._rerank_snapshot(_RERANK, process)


def test_capture_uses_existing_embedding_snapshot_without_inference(
        monkeypatch: pytest.MonkeyPatch) -> None:
    process, calls = _fake_process()

    class FakeEmbedding:
        def __init__(self, container: str, *, process: Any) -> None:
            assert container == _EMBED and process is invoke

        def snapshot(self) -> dict[str, Any]:
            return {"container": {"id": _EMBED}, "model": {"revision": "frozen"}}

    invoke = process
    monkeypatch.setattr(identity, "_support",
                        lambda: (FakeEmbedding, ValueError, invoke))
    model_sha = sha256(canonical_bytes({"revision": "frozen"})).hexdigest()
    result = identity.capture_model_identity(_EMBED, _RERANK, model_sha,
                                             process=invoke)
    assert result["schemaVersion"] == 1 and len(result["sha256"]) == 64
    assert result["embedding"]["container"]["id"] == _EMBED
    assert [call[1] for call in calls] == ["inspect", "exec"]
    with pytest.raises(identity.BModelIdentityError):
        identity.capture_model_identity(_EMBED, _RERANK, "0" * 64,
                                        process=invoke)


def test_container_ids_are_exact_and_distinct() -> None:
    for first, second in ((_EMBED[:-1], _RERANK), (_EMBED, _EMBED),
                          ("x" * 64, _RERANK)):
        with pytest.raises(identity.BModelIdentityError):
            identity.capture_model_identity(first, second,
                                            "0" * 64,
                                            process=lambda *_: b"{}")


def test_locked_environment_rejects_dependency_drift(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata, "version", lambda _: "0.0.0")
    with pytest.raises(identity.BModelIdentityError):
        identity._require_locked_corpus_environment()


def test_identity_environment_locks_only_actual_import_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    def version(name: str) -> str:
        calls.append(name)
        return {"httpx": "0.28.1", "pydantic": "2.13.5"}.get(name, "parser-drift")
    monkeypatch.setattr(metadata, "version", version)
    identity._require_locked_identity_environment()
    assert set(calls) == {"httpx", "pydantic"} and len(calls) == 2
    with pytest.raises(identity.BModelIdentityError):
        identity._require_locked_corpus_environment()


@pytest.mark.parametrize("dependency", ["httpx", "pydantic"])
def test_identity_environment_rejects_required_dependency_drift(
        monkeypatch: pytest.MonkeyPatch, dependency: str) -> None:
    monkeypatch.setattr(metadata, "version", lambda name:
        "0.0.0" if name == dependency else {"httpx": "0.28.1", "pydantic": "2.13.5"}[name])
    with pytest.raises(identity.BModelIdentityError):
        identity._require_locked_identity_environment()


def test_identity_environment_still_requires_python312(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 11, 0))
    with pytest.raises(identity.BModelIdentityError):
        identity._require_locked_identity_environment()


def test_cli_rejects_extra_input_without_snapshot(
        monkeypatch: pytest.MonkeyPatch) -> None:
    class Stream:
        def __init__(self, payload: bytes = b"") -> None:
            self.buffer = BytesIO(payload)

    monkeypatch.setattr(identity, "_require_locked_corpus_environment", lambda: None)
    monkeypatch.setattr(sys, "stdin", Stream(b'{"extra":1}\n'))
    output = Stream()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(identity, "capture_model_identity",
                        lambda *_: pytest.fail("snapshot must not run"))
    assert identity.main() == 1
    assert output.buffer.getvalue() == b'{"status":"model_identity_invalid"}\n'
