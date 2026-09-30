"""Read-only local model identity for one bounded B comparison window.

This module inspects Docker metadata and hashes cached model bytes. It never
calls the embedding/rerank HTTP endpoints or loads a model for inference.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import sys
import tomllib
from collections.abc import Callable
from typing import Any

_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
_INSPECT = ('{"id":{{json .Id}},"image":{{json .Image}},'
            '"started":{{json .State.StartedAt}},"running":{{json .State.Running}},'
            '"path":{{json .Path}},"args":{{json .Args}},'
            '"ports":{{json .NetworkSettings.Ports}}}')
_RERANK_HASHES = {
    "model.safetensors": "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286",
    "config.json": "13dcd6c31d9fec9d1d8e158702072f62d7fa7d312a64b9fe057bec9a08cfe41a",
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
    "special_tokens_map.json": "8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835",
    "tokenizer.json": "69564b696052886ed0ac63fa393e928384e0f8caada38c1f4864a9bfbf379c15",
    "tokenizer_config.json": "7e4c1cc848840aeccdd763458c18dd525eb0f795c992e00ebe9c28554e7db2d4",
}
_RERANK_PROBE = r'''
import hashlib, importlib.metadata, json, pathlib, sys
from datetime import datetime
payload = json.load(sys.stdin)
started = datetime.fromisoformat(payload["started"].replace("Z", "+00:00")).timestamp()
root = pathlib.Path("/root/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3")
ref = (root / "refs/main").read_text().strip()
assert ref == payload["revision"]
snap = root / "snapshots" / ref
assert snap.is_dir() and snap.stat().st_mtime < started
assert {p.name for p in (root / "snapshots").iterdir()} == {ref}
files = {}
for name in payload["files"]:
    path = snap / name
    before = path.stat()
    assert before.st_mtime < started
    with path.open("rb") as stream:
        value = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    files[name] = value
service = pathlib.Path("/app/reranker_server.py")
before = service.stat()
assert before.st_mtime < started
with service.open("rb") as stream:
    service_sha = hashlib.file_digest(stream, "sha256").hexdigest()
after = service.stat()
assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
assert (root / "refs/main").read_text().strip() == ref
print(json.dumps({"revision": ref, "files": files,
 "serviceSha256": service_sha,
 "packages": {name: importlib.metadata.version(name)
              for name in ("FlagEmbedding", "transformers", "torch")}}))
'''
_Process = Callable[[list[str], bytes], bytes]


class BModelIdentityError(ValueError):
    """Finite failure; no container output or model data appears in the error."""

    def __init__(self) -> None:
        super().__init__("model_identity_invalid")


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _require_locked_corpus_environment() -> None:
    """Check Python and all project runtime pins before importing parser/model code."""
    if sys.version_info[:2] != (3, 12):
        raise BModelIdentityError()
    try:
        project = Path(__file__).resolve().parents[2] / "pyproject.toml"
        manifest = tomllib.loads(project.read_text(encoding="utf-8"))
        dependencies = manifest["project"]["dependencies"]
        if type(dependencies) is not list or not dependencies:
            raise BModelIdentityError()
        for dependency in dependencies:
            if type(dependency) is not str or (match := re.fullmatch(
                    r"([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][A-Za-z0-9._+-]*)",
                    dependency)) is None:
                raise BModelIdentityError()
            if metadata.version(match.group(1)) != match.group(2):
                raise BModelIdentityError()
    except (KeyError, OSError, UnicodeError, ValueError, metadata.PackageNotFoundError):
        raise BModelIdentityError() from None


def _support() -> tuple[Any, Any, _Process]:
    from .local_vector_preparation import (  # noqa: PLC0415
        LocalVectorPreparation, PreparationError, run_process,
    )
    return LocalVectorPreparation, PreparationError, run_process


def _parse(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BModelIdentityError()
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(BModelIdentityError()))
    except (ValueError, UnicodeError):
        raise BModelIdentityError() from None


def _container_id(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _rerank_snapshot(container_id: str, process: _Process) -> dict[str, Any]:
    identity = _parse(process(["docker", "inspect", "--format", _INSPECT,
                               container_id], b""))
    if (type(identity) is not dict
            or set(identity) != {"id", "image", "started", "running", "path", "args", "ports"}
            or identity["id"] != container_id or identity["running"] is not True
            or type(identity["image"]) is not str
            or re.fullmatch(r"sha256:[a-f0-9]{64}", identity["image"]) is None
            or type(identity["started"]) is not str
            or re.fullmatch(r"[0-9TZ:.+-]{20,40}", identity["started"]) is None
            or type(identity["path"]) is not str or not identity["path"]
            or type(identity["args"]) is not list
            or any(type(arg) is not str for arg in identity["args"])):
        raise BModelIdentityError()
    ports = identity["ports"]
    if (type(ports) is not dict or set(ports) != {"8909/tcp"}
            or type(ports["8909/tcp"]) is not list or not ports["8909/tcp"]
            or any(type(port) is not dict or set(port) != {"HostIp", "HostPort"}
                   or port["HostIp"] not in ("0.0.0.0", "127.0.0.1", "::")
                   or port["HostPort"] != "8909" for port in ports["8909/tcp"])):
        raise BModelIdentityError()
    model = _parse(process(["docker", "exec", "-i", container_id,
                            "python", "-B", "-c", _RERANK_PROBE],
                           _canonical({"started": identity["started"],
                                            "revision": _REVISION,
                                            "files": sorted(_RERANK_HASHES)})))
    if (type(model) is not dict or set(model) != {
                "revision", "files", "packages", "serviceSha256"}
            or model["revision"] != _REVISION or model["files"] != _RERANK_HASHES
            or type(model["serviceSha256"]) is not str
            or re.fullmatch(r"[a-f0-9]{64}", model["serviceSha256"]) is None
            or type(model["packages"]) is not dict
            or set(model["packages"]) != {"FlagEmbedding", "transformers", "torch"}
            or any(type(value) is not str
                   or re.fullmatch(r"[0-9A-Za-z.+-]{1,32}", value) is None
                   for value in model["packages"].values())):
        raise BModelIdentityError()
    # Docker argv can contain operator-provided values. Its hash is enough to
    # prove pre/post stability without persisting command-line contents.
    safe_container = {key: value for key, value in identity.items()
                      if key not in ("path", "args")}
    safe_container["pathSha256"] = hashlib.sha256(identity["path"].encode()).hexdigest()
    safe_container["argsSha256"] = hashlib.sha256(_canonical(identity["args"])).hexdigest()
    return {"container": safe_container, "model": model}


def capture_model_identity(embedding_container_id: str,
                           rerank_container_id: str,
                           expected_embedding_model_sha256: str,
                           *, process: _Process | None = None) -> dict[str, Any]:
    """Return finite identities for pre/post comparison; no inference occurs."""
    if (not _container_id(embedding_container_id)
            or not _container_id(rerank_container_id)
            or embedding_container_id == rerank_container_id
            or type(expected_embedding_model_sha256) is not str
            or re.fullmatch(r"[a-f0-9]{64}", expected_embedding_model_sha256) is None):
        raise BModelIdentityError()
    preparation, preparation_error, default_process = _support()
    processor = default_process if process is None else process
    try:
        embedding = preparation(embedding_container_id,
                                process=processor).snapshot()
        rerank = _rerank_snapshot(rerank_container_id, processor)
    except (preparation_error, OSError, ValueError):
        raise BModelIdentityError() from None
    if (hashlib.sha256(_canonical(embedding["model"])).hexdigest()
            != expected_embedding_model_sha256):
        raise BModelIdentityError()
    return {"schemaVersion": 1, "embedding": embedding, "rerank": rerank,
            "sha256": hashlib.sha256(_canonical({
                "embedding": embedding, "rerank": rerank})).hexdigest()}


def main() -> int:
    try:
        _require_locked_corpus_environment()
        raw = sys.stdin.buffer.read(2049)
        value = _parse(raw)
        if (len(raw) > 2048 or type(value) is not dict
                or set(value) != {"embeddingContainerId", "rerankContainerId",
                                  "expectedEmbeddingModelSha256"}):
            raise BModelIdentityError()
        result = capture_model_identity(value["embeddingContainerId"],
                                        value["rerankContainerId"],
                                        value["expectedEmbeddingModelSha256"])
        encoded = _canonical(result)
        if len(encoded) > 32768:
            raise BModelIdentityError()
        sys.stdout.buffer.write(encoded)
        return 0
    except BModelIdentityError:
        sys.stdout.buffer.write(b'{"status":"model_identity_invalid"}\n')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
