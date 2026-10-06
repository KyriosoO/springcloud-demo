"""Private identity preparation, not an executor or an operation grant.

The caller supplies an independently authorized, bounded process provider.
Only existing read-only model probes are accepted; no inference, default
Docker discovery, HTTP, CLI, old batch input or authorization writer exists.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from threading import Lock

from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence import catalog as policy_source
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_projection as projection
from tests.evaluation.knowledge.rebuild_b_local_runner import (
    _RUNTIME_CONFIG_FILES, _frozen_runtime_config_dir, _git_bytes,
)
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding

Process = Callable[[list[str], bytes], bytes]
Checkpoint = Callable[[str, int | None, "IdentityAttempt | None"], None]


@dataclass(frozen=True, slots=True)
class IdentityAttempt:
    phase: str
    ordinal: int
    command_sha256: str
    input_sha256: str
    outcome: str = "pending"


class IdentityLedger:
    """Four separately counted local process attempts per allowed phase.

    Checkpoints happen before the provider boundary. This ledger does not
    attest the checkpoint's durability or the provider's authorization.
    """
    def __init__(self, *, phases: tuple[str, ...], checkpoint: Checkpoint) -> None:
        p.require(phases in (("preparation",), ("pre", "post")) and callable(checkpoint),
                  "identity_ledger_invalid")
        self.phases, self.checkpoint = phases, checkpoint
        self._events: list[IdentityAttempt] = []
        self._stopped = False
        self._lock = Lock()

    def _write(self, event: str, ticket: int | None, attempt: IdentityAttempt | None) -> None:
        failed = False
        try:
            self.checkpoint(event, ticket, attempt)
        except Exception:
            failed = True
        if failed:
            self._stopped = True
            raise p.ProtocolError("identity_checkpoint_failed") from None

    def begin(self, phase: str, ordinal: int, command: list[str], raw: bytes) -> int:
        p.require(type(phase) is str and phase in self.phases and type(ordinal) is int
            and 0 <= ordinal < 4 and type(command) is list and 1 <= len(command) <= 12
            and all(type(value) is str and 0 < len(value) <= 8192 for value in command)
            and type(raw) is bytes and len(raw) <= 2048, "identity_attempt_invalid")
        with self._lock:
            p.require(not self._stopped, "identity_stopped")
            previous = [attempt for attempt in self._events if attempt.phase == phase]
            p.require(len(previous) == ordinal and all(row.outcome == "completed" for row in previous),
                      "identity_retry_forbidden")
            attempt = IdentityAttempt(phase, ordinal, sha256(p.canonical(command)).hexdigest(),
                                      sha256(raw).hexdigest())
            ticket = len(self._events)
            self._events.append(attempt)
            self._write("started", ticket, attempt)
            return ticket

    def finish(self, ticket: int, *, failed: bool) -> None:
        p.require(type(ticket) is int and type(failed) is bool, "identity_receipt_invalid")
        with self._lock:
            p.require(0 <= ticket < len(self._events), "identity_receipt_invalid")
            row = self._events[ticket]
            p.require(row.outcome == "pending", "identity_receipt_invalid")
            receipt = IdentityAttempt(row.phase, row.ordinal, row.command_sha256, row.input_sha256,
                                      "process_failed" if failed else "completed")
            self._write("finished", ticket, receipt)
            self._events[ticket] = receipt
            if failed:
                self._stopped = True

    def abort(self) -> None:
        with self._lock:
            if not self._stopped:
                self._stopped = True
                self._write("stopped", None, None)

    def view(self) -> dict[str, object]:
        with self._lock:
            return {"counts": {phase: sum(row.phase == phase for row in self._events) for phase in self.phases},
                "pending": sum(row.outcome == "pending" for row in self._events),
                "stopped": self._stopped, "events": [asdict(row) for row in self._events]}


def _sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _file_hash(path: Path, maximum: int = 64 * 1024 * 1024) -> str:
    p.require(path.is_absolute() and path.resolve() == path and path.is_file()
        and not path.is_symlink() and 0 < path.stat().st_size <= maximum, "identity_file_invalid")
    with path.open("rb") as stream:
        before = path.stat()
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = path.stat()
    p.require((before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino), "identity_file_drift")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ModelBinding:
    embedding_container_id: str
    rerank_container_id: str
    embedding_model_sha256: str
    docker: Path
    docker_sha256: str
    docker_host: str

    def __post_init__(self) -> None:
        p.require(all(_sha(value) for value in (self.embedding_container_id, self.rerank_container_id,
            self.embedding_model_sha256, self.docker_sha256))
            and self.embedding_container_id != self.rerank_container_id
            and self.docker_host in ("npipe:////./pipe/docker_engine", "unix:///var/run/docker.sock")
            and isinstance(self.docker, Path) and self.docker.is_absolute(), "identity_model_binding_invalid")

    def verify_executable(self) -> None:
        p.require(_file_hash(self.docker) == self.docker_sha256, "identity_docker_drift")


@dataclass(frozen=True, slots=True)
class IdentityCapture:
    static_sha256: str
    model_sha256: str
    identity_sha256: str
    material: bytes = field(repr=False)

    def preview(self) -> dict[str, object]:
        return {"kind": "document_number_identity_capture_v1", "staticSha256": self.static_sha256,
            "modelSha256": self.model_sha256, "identitySha256": self.identity_sha256,
            "executionAuthorityGranted": False, "qualityAssessment": "Not assessed"}


def capture_static_identity(pair: projection.ProjectedJavaPair, binding: ReadBinding) -> bytes:
    """Actual leased binaries/config and current catalog, not supplied labels.

    Catalog identity does not prove read or egress permission, nor exercise
    Evidence/Summary. Git reads and file reads are separate non-HTTP work.
    """
    pair.verify_artifacts()
    binding.__post_init__()
    projection._validate_pair(pair.proofs, pair.draft)
    head = pair.draft.frozen_head
    p.require(_git_bytes("rev-parse", "HEAD").decode().strip() == head
        and not _git_bytes("status", "--porcelain=v1", "--untracked-files=no").strip(),
        "identity_repository_drift")
    config_raw = _git_bytes("show", f"{head}:{projection.CONFIG}")
    arms: list[dict[str, object]] = []
    for jar, config, proof in zip(pair.jars, pair.configs, pair.proofs, strict=True):
        frozen_config, expected_shared = _frozen_runtime_config_dir(jar, head)
        p.require(frozen_config == config, "identity_config_path_drift")
        jar_raw = jar.read_bytes()
        _, fingerprints = projection._artifacts(jar_raw, config_raw=config_raw)
        p.require(sha256(jar_raw).hexdigest() == proof.jar_sha256
            and sha256(config_raw).hexdigest() == proof.config_sha256
            and fingerprints == (proof.shared_classes_sha256, proof.dependencies_sha256,
                                  proof.helper_classes_sha256), "identity_projection_drift")
        shared = {name: _file_hash(config / name, 2 * 1024 * 1024) for name in _RUNTIME_CONFIG_FILES}
        p.require(shared == expected_shared, "identity_shared_config_drift")
        arms.append({"arm": proof.arm, "jarSha256": proof.jar_sha256,
            "configSha256": proof.config_sha256, "sharedConfig": shared,
            "sharedClassesSha256": proof.shared_classes_sha256,
            "dependenciesSha256": proof.dependencies_sha256, "helperClassesSha256": proof.helper_classes_sha256,
            "inspectorSha256": proof.inspector_sha256, "projectionRows": [asdict(row) for row in proof.rows]})
    catalog = KnowledgeEgressPolicyCatalog.load_current_resource().snapshot
    from knowledge_corpus_tools import b_model_identity_v1 as models
    from knowledge_corpus_tools import local_vector_preparation as embed
    sources = (
        (policy_source.__file__, "agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py"),
        (models.__file__, "knowledge-corpus-tools/src/knowledge_corpus_tools/b_model_identity_v1.py"),
        (embed.__file__, "knowledge-corpus-tools/src/knowledge_corpus_tools/local_vector_preparation.py"),
        (str(Path(__file__)), "agent-runtime/tests/evaluation/knowledge/rebuild_document_number_identity.py"),
    )
    source_hashes = {}
    for actual, relative in sources:
        source_path = Path(actual).resolve()
        p.require(source_path == (p.ROOT / relative).resolve(), "identity_source_path_drift")
        source_hashes[relative] = _file_hash(source_path, 2 * 1024 * 1024)
        p.require(source_hashes[relative] == sha256(_git_bytes("show", f"{head}:{relative}")).hexdigest(),
                  "identity_source_drift")
    raw = p.canonical({"frozenHead": head, "binding": asdict(binding), "arms": arms,
        "javaSha256": _file_hash(pair.java), "sourceSha256": source_hashes, "profiles": {
            domain: binding.profile_snapshot(domain) for domain in ("tax.policy", "tax.law")},
        "catalog": {"sourceSha256": catalog.source_sha256, "canonicalFingerprint": catalog.canonical_fingerprint,
            "catalogVersion": catalog.catalog_version, "authorityId": catalog.authority_id,
            "exportId": catalog.export_id, "sourceRevision": catalog.source_revision}})
    p.require(len(raw) <= 32768, "identity_static_size_invalid")
    return raw


class IdentitySession:
    """One preparation, or ordered pre/post identity checks on one ledger.

    No default process provider: the outer executor owns authorization, a
    bounded provider and durable journal. The cached output is identity only.
    """
    def __init__(self, *, pair: projection.ProjectedJavaPair, binding: ReadBinding,
                 model: ModelBinding, ledger: IdentityLedger, process: Process,
                 expected: IdentityCapture | None = None) -> None:
        p.require(type(pair) is projection.ProjectedJavaPair and type(binding) is ReadBinding
            and type(model) is ModelBinding and type(ledger) is IdentityLedger and callable(process)
            and ledger.phases == (("preparation",) if expected is None else ("pre", "post")),
            "identity_session_invalid")
        model.__post_init__()
        p.require(expected is None or type(expected) is IdentityCapture and _sha(expected.static_sha256)
            and _sha(expected.model_sha256) and _sha(expected.identity_sha256)
            and type(expected.material) is bytes and 0 < len(expected.material) <= 65536
            and sha256(expected.material).hexdigest() == expected.identity_sha256,
            "identity_expected_invalid")
        self.pair, self.binding, self.model, self.ledger, self.process = pair, binding, model, ledger, process
        self.expected = expected
        self._attempted: list[str] = []
        self._completed: list[str] = []
        self._active = False
        self._rejected = False
        self._lock = Lock()
        # Finite diagnostics for the owning executor, including failed runs.
        # These never turn a failed comparison into an accepted identity.
        self.failure_phase: str | None = None
        self.observed: IdentityCapture | None = None

    def capture(self, phase: str) -> IdentityCapture:
        with self._lock:
            valid = not self._active and not self._rejected and (
                self.expected is None and phase == "preparation" and not self._attempted
                or self.expected is not None and (phase == "pre" and not self._attempted
                    or phase == "post" and self._attempted == self._completed == ["pre"]))
            if valid:
                self._attempted.append(phase)
                self._active = True
                self.failure_phase = None
                self.observed = None
            else:
                self._rejected = True
                if not self._active:
                    self.failure_phase = "phase_invalid"
                    self.observed = None
        if not valid:
            self.ledger.abort()
            raise p.ProtocolError("identity_phase_invalid")
        result: IdentityCapture | None = None
        failed = False
        failure_phase = "static_identity"
        try:
            from knowledge_corpus_tools import b_model_identity_v1 as models
            from knowledge_corpus_tools import local_vector_preparation as embed
            # Calling the existing collector directly must not bypass its CLI's
            # project environment lock. This check makes no Docker/model call.
            models._require_locked_corpus_environment()
            static = capture_static_identity(self.pair, self.binding)
            p.require(self.expected is None or sha256(static).hexdigest() == self.expected.static_sha256,
                      "identity_static_drift")
            failure_phase = "model_capture"
            self.model.verify_executable()
            ordinal = 0
            def counted(command: list[str], raw: bytes) -> bytes:
                nonlocal ordinal
                container = self.model.embedding_container_id if ordinal < 2 else self.model.rerank_container_id
                expected_command = (["docker", "inspect", "--format", embed._INSPECT, container]
                    if ordinal in (0, 2) else ["docker", "exec", "-i", container, "python", "-B", "-c",
                        embed._PROBE if ordinal == 1 else models._RERANK_PROBE])
                p.require(ordinal < 4 and command == expected_command, "identity_command_invalid")
                self.model.verify_executable()
                local = [str(self.model.docker), "--host", self.model.docker_host, *command[1:]]
                ticket = self.ledger.begin(phase, ordinal, local, raw)
                ordinal += 1
                output: bytes | None = None
                error = False
                try:
                    output = self.process(local, raw)
                    p.require(type(output) is bytes and 0 < len(output) <= 65536, "identity_output_invalid")
                except Exception:
                    error = True
                self.ledger.finish(ticket, failed=error)
                p.require(not error and output is not None, "identity_process_failed")
                assert output is not None
                return output
            snapshot = models.capture_model_identity(self.model.embedding_container_id,
                self.model.rerank_container_id, self.model.embedding_model_sha256, process=counted)
            failure_phase = "static_recheck"
            p.require(ordinal == 4 and capture_static_identity(self.pair, self.binding) == static,
                      "identity_static_drift")
            self.model.verify_executable()
            failure_phase = "material_encoding"
            material = p.canonical({"static": p._decode(static), "models": snapshot,
                "docker": {"host": self.model.docker_host, "executableSha256": self.model.docker_sha256}})
            p.require(len(material) <= 65536, "identity_material_size_invalid")
            result = IdentityCapture(sha256(static).hexdigest(), snapshot["sha256"],
                                     sha256(material).hexdigest(), material)
            self.observed = result
            failure_phase = "expected_comparison"
            p.require(self.expected is None or result == self.expected, "identity_observed_drift")
        except Exception:
            failed = True
        with self._lock:
            state = self.ledger.view()
            failed = failed or self._rejected or bool(state["stopped"]) or state["pending"] != 0
            self._active = False
            if not failed:
                self._completed.append(phase)
        if failed:
            self.failure_phase = failure_phase
            self.ledger.abort()
            raise p.ProtocolError("identity_capture_failed") from None
        assert result is not None
        return result

    async def capture_async(self, phase: str) -> IdentityCapture:
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            self.ledger.abort()
            raise asyncio.CancelledError
        task = asyncio.create_task(asyncio.to_thread(self.capture, phase))
        cancelled = stop_failed = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
                try:
                    self.ledger.abort()
                except Exception:
                    stop_failed = True
            except Exception:
                break
        if cancelled:
            if not task.cancelled():
                task.exception()
            if stop_failed:
                raise p.ProtocolError("identity_cancel_stop_failed") from None
            raise asyncio.CancelledError from None
        return task.result()
