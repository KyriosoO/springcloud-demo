"""DR-KRET-031 local-only model identity and no-truncation preparation.

The existing model container supplies its tokenizer; this offline tool adds no
model dependency and never imports the running embedding server in a new process.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from typing import Any

import httpx

from .errors import ContractError
from .vector_candidate import _reject_constant, _unique_pairs, _vector_bytes, canonical_bytes
from .vector_representation import VectorRepresentation

SERVICE_SHA = "8a9e118c404e2ca9d67cc4cb7defb5f6662eafe4804bc739df69781d98c8f522"
MODEL_FILES = (
    "config.json", "config_sentence_transformers.json", "modules.json",
    "sentence_bert_config.json", "special_tokens_map.json", "tokenizer_config.json",
    "tokenizer.json", "sentencepiece.bpe.model", "pytorch_model.bin",
    "colbert_linear.pt", "sparse_linear.pt",
)
_INSPECT = ('{"id":{{json .Id}},"image":{{json .Image}},'
            '"started":{{json .State.StartedAt}},"running":{{json .State.Running}},'
            '"path":{{json .Path}},"args":{{json .Args}},'
            '"ports":{{json .NetworkSettings.Ports}}}')

# No text/vector is written to disk or stdout by either container program.
_PROBE = r'''
import hashlib, importlib.metadata, json, pathlib, sys
from datetime import datetime
payload = json.load(sys.stdin)
started = datetime.fromisoformat(payload["started"].replace("Z", "+00:00")).timestamp()
root = pathlib.Path("/root/.cache/huggingface/hub/models--BAAI--bge-m3")
ref = root / "refs/main"
revision = ref.read_text().strip()
assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
snapshot = root / "snapshots" / revision
# HuggingFace refreshes refs/main during startup. Prove the unique actual
# snapshot and all weight/tokenizer bytes predate startup, not the mutable ref.
assert {p.name for p in (root / "snapshots").iterdir()} == {revision}
assert (root / "snapshots").stat().st_mtime < started
assert snapshot.stat().st_mtime < started
def digest(path, prestart=True):
    before = path.stat()
    assert not prestart or before.st_mtime < started
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {"bytes": after.st_size, "sha256": h.hexdigest()}
files = {name: digest(snapshot / name) for name in payload["files"]}
service = digest(pathlib.Path("/app/embedding_server.py"))
implementation = digest(pathlib.Path("/opt/conda/lib/python3.11/site-packages/FlagEmbedding/inference/embedder/encoder_only/m3.py"))
assert ref.read_text().strip() == revision
print(json.dumps({"revision": revision, "files": files, "service": service,
 "implementation": implementation, "max_length": 1024,
 "cache_provenance": "single_snapshot_predates_start",
 "packages": {name: importlib.metadata.version(name) for name in ("FlagEmbedding", "transformers", "torch")}}))
'''

_TOKENS = r'''
import json, os, pathlib, sys
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
payload = json.load(sys.stdin)
root = pathlib.Path("/root/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots") / payload["revision"]
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
values = tokenizer(payload["texts"], add_special_tokens=True, truncation=False, padding=False)["input_ids"]
print(json.dumps([len(value) for value in values]))
'''


class PreparationError(ContractError):
    def __init__(self, reason: str):
        self.reason = reason if reason in {
            "process_failed", "identity_invalid", "identity_changed", "tokens_invalid",
            "tokens_exceeded", "input_invalid", "embedding_invalid", "already_consumed",
        } else "identity_invalid"
        super().__init__(self.reason)


def run_process(command: list[str], payload: bytes) -> bytes:
    """No shell, no model credentials inherited, bounded diagnostic output."""
    environment = {key: os.environ[key] for key in (
        "PATH", "SystemRoot", "USERPROFILE", "LOCALAPPDATA", "TEMP", "TMP",
    ) if key in os.environ}
    output: bytes | None = None
    try:
        result = subprocess.run(command, input=payload, capture_output=True,
                                timeout=120, env=environment, check=False)
        if result.returncode == 0 and len(result.stdout) <= 65536:
            output = result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    if output is None:
        raise PreparationError("process_failed")
    return output


def _json(raw: bytes) -> Any:
    value: Any = None
    ok = False
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        ok = True
    except (ValueError, UnicodeError):
        pass
    if not ok:
        raise PreparationError("identity_invalid")
    return value


def _digest_valid(value: Any) -> bool:
    return (type(value) is dict and set(value) == {"bytes", "sha256"}
            and type(value["bytes"]) is int and value["bytes"] > 0
            and type(value["sha256"]) is str
            and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is not None)


class LocalVectorPreparation:
    def __init__(self, container: str, *, process: Callable[[list[str], bytes], bytes] = run_process,
                 transport: httpx.BaseTransport | None = None):
        if type(container) is not str or not re.fullmatch(r"[a-f0-9]{64}", container):
            raise PreparationError("identity_invalid")
        self.container = container
        self._process = process
        self._transport = transport
        self._snapshot: bytes | None = None
        self.consumed = False
        self.http_calls = 0
        self.text_count = 0
        self.max_tokens = 0
        self.failure_reason: str | None = None

    def _container(self, program: str, payload: Any) -> Any:
        return _json(self._process(["docker", "exec", "-i", self.container,
                                   "python", "-B", "-c", program], canonical_bytes(payload)))

    def snapshot(self) -> dict[str, Any]:
        identity = _json(self._process(["docker", "inspect", "--format", _INSPECT,
                                       self.container], b""))
        if (type(identity) is not dict or set(identity) != {
                "id", "image", "started", "running", "path", "args", "ports"}
                or identity["id"] != self.container or identity["running"] is not True
                or type(identity["image"]) is not str
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", identity["image"])
                or type(identity["started"]) is not str
                or not re.fullmatch(r"[0-9TZ:.+-]{20,40}", identity["started"])
                or identity["path"] != "python"
                or identity["args"] != ["-m", "uvicorn", "embedding_server:app", "--host",
                                        "0.0.0.0", "--port", "8908"]):
            raise PreparationError("identity_invalid")
        ports = identity["ports"]
        if (type(ports) is not dict or set(ports) != {"8908/tcp"}
                or type(ports["8908/tcp"]) is not list or not ports["8908/tcp"]
                or any(type(p) is not dict or set(p) != {"HostIp", "HostPort"}
                       or p["HostIp"] not in ("0.0.0.0", "127.0.0.1", "::")
                       or p["HostPort"] != "8908" for p in ports["8908/tcp"])):
            raise PreparationError("identity_invalid")
        model = self._container(_PROBE, {"started": identity["started"], "files": MODEL_FILES})
        if (type(model) is not dict or set(model) != {
                "revision", "files", "service", "implementation", "max_length", "packages",
                "cache_provenance"}
                or type(model["revision"]) is not str
                or not re.fullmatch(r"[a-f0-9]{40}", model["revision"])
                or model["cache_provenance"] != "single_snapshot_predates_start"
                or model["max_length"] != 1024 or type(model["max_length"]) is not int
                or type(model["files"]) is not dict or set(model["files"]) != set(MODEL_FILES)
                or not all(_digest_valid(v) for v in model["files"].values())
                or not _digest_valid(model["service"]) or model["service"]["sha256"] != SERVICE_SHA
                or not _digest_valid(model["implementation"])
                or type(model["packages"]) is not dict
                or set(model["packages"]) != {"FlagEmbedding", "transformers", "torch"}
                or any(type(v) is not str or not re.fullmatch(r"[0-9A-Za-z.+-]{1,32}", v)
                       for v in model["packages"].values())):
            raise PreparationError("identity_invalid")
        return {"container": identity, "model": model}

    def freeze(self) -> dict[str, Any]:
        if self._snapshot is not None:
            raise PreparationError("already_consumed")
        snapshot = self.snapshot()
        self._snapshot = canonical_bytes(snapshot)
        return snapshot

    @property
    def snapshot_sha256(self) -> str:
        if self._snapshot is None:
            raise PreparationError("identity_invalid")
        return hashlib.sha256(self._snapshot).hexdigest()

    def _prepare(self, items: tuple[VectorRepresentation, ...]) -> tuple[tuple[float, ...], ...]:
        if self.consumed or self._snapshot is None:
            raise PreparationError("already_consumed")
        self.consumed = True
        if (type(items) is not tuple or not 1 <= len(items) <= 1000
                or any(type(item) is not VectorRepresentation for item in items)):
            raise PreparationError("input_invalid")
        if canonical_bytes(self.snapshot()) != self._snapshot:
            raise PreparationError("identity_changed")
        revision = _json(self._snapshot)["model"]["revision"]
        counts = self._container(_TOKENS, {"revision": revision, "texts": [i.text for i in items]})
        if (type(counts) is not list or len(counts) != len(items)
                or any(type(n) is not int or n < 1 for n in counts)):
            raise PreparationError("tokens_invalid")
        self.max_tokens = max(counts)
        if self.max_tokens > 1024:
            raise PreparationError("tokens_exceeded")
        vectors: list[tuple[float, ...]] = []
        transport = self._transport if self._transport is not None else httpx.HTTPTransport(retries=0)
        with httpx.Client(base_url="http://127.0.0.1:8908", timeout=30, trust_env=False,
                          follow_redirects=False, transport=transport) as client:
            for start in range(0, len(items), 32):
                batch = items[start:start + 32]
                self.http_calls += 1
                self.text_count += len(batch)
                raw = bytearray()
                began = time.monotonic()
                with client.stream("POST", "/embed", json={"texts": [i.text for i in batch]}) as response:
                    if response.status_code != 200:
                        raise PreparationError("embedding_invalid")
                    for block in response.iter_bytes():
                        raw.extend(block)
                        if len(raw) > 2 * 1024 * 1024 or time.monotonic() - began > 30:
                            raise PreparationError("embedding_invalid")
                decoded = _json(bytes(raw))
                if (type(decoded) is not dict or set(decoded) != {"dim", "vectors"}
                        or type(decoded["dim"]) is not int or decoded["dim"] != 1024
                        or type(decoded["vectors"]) is not list or len(decoded["vectors"]) != len(batch)):
                    raise PreparationError("embedding_invalid")
                for vector in decoded["vectors"]:
                    _vector_bytes(vector)
                    vectors.append(tuple(float(x) for x in vector))
        if canonical_bytes(self.snapshot()) != self._snapshot:
            raise PreparationError("identity_changed")
        return tuple(vectors)

    def __call__(self, items: tuple[VectorRepresentation, ...]) -> tuple[tuple[float, ...], ...]:
        # Sanitize failures outside the except block, including provider contexts.
        reason = "embedding_invalid"
        try:
            return self._prepare(items)
        except PreparationError as error:
            reason = error.reason
        except Exception:
            pass
        self.failure_reason = reason
        raise PreparationError(reason)
