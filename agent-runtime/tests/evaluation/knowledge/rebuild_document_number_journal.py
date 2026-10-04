"""Private append-only attempt evidence, never a launcher or authorization.

Tests create synthetic logs only. A future live executor must validate its own
frozen authorization, snapshots and owned resources before using this writer.
No response bodies, credentials, vectors or exception objects enter the API.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
from threading import Lock
from typing import BinaryIO

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_transport import Attempt, AttemptLedger


@dataclass(frozen=True, slots=True)
class JournalBinding:
    run_id: str
    frozen_head: str
    protocol_sha256: str
    projection_sha256: str
    snapshot_sha256: str
    authorization_sha256: str
    evidence_kind: str

    def __post_init__(self) -> None:
        pattern = (r"synthetic-document-number-[0-9]{3}" if self.evidence_kind == "synthetic_non_live"
                   else r"knowledge-document-number-[0-9]{8}-[0-9]{2}")
        p.require(type(self.evidence_kind) is str and self.evidence_kind in ("synthetic_non_live", "live_attempts")
            and type(self.run_id) is str and re.fullmatch(pattern, self.run_id) is not None
            and type(self.frozen_head) is str and re.fullmatch(r"[0-9a-f]{40}", self.frozen_head) is not None
            and all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
                    for value in (self.protocol_sha256, self.projection_sha256,
                                  self.snapshot_sha256, self.authorization_sha256)), "journal_binding_invalid")


@dataclass(frozen=True, slots=True)
class CleanupReport:
    processes_stopped: bool
    clients_closed: bool
    proxy_stopped: bool
    ports_released: bool

    def __post_init__(self) -> None:
        p.require(all(type(value) is bool for value in asdict(self).values()), "journal_cleanup_invalid")


class AttemptJournal:
    """Exclusive new log; durable checkpoints are inside the ledger order lock.

    This class owns only its file handle. Cleanup fields are caller reports,
    not proof that any process, client, proxy or port has actually been closed.
    """
    def __init__(self, *, directory: Path, binding: JournalBinding,
                 limits: tuple[tuple[str, int], ...]) -> None:
        p.require(type(binding) is JournalBinding, "journal_binding_invalid")
        binding.__post_init__()
        p.require(directory.name == binding.run_id and directory.parent.is_dir()
                  and directory.parent.resolve() == directory.parent.absolute(), "journal_path_invalid")
        self._lock = Lock()
        self._broken = False
        self._closed = False
        self._sequence = 0
        self._size = 0
        self._hash = sha256()
        self._stream: BinaryIO | None = None
        self._path = directory / "attempts.jsonl"
        self._identity: tuple[int, int] | None = None
        self.ledger = AttemptLedger(limits, checkpoint=self._checkpoint)
        failed = False
        try:
            directory.mkdir(parents=False, exist_ok=False)
            self._stream = self._path.open("xb")
            identity = os.fstat(self._stream.fileno())
            self._identity = (identity.st_dev, identity.st_ino)
        except OSError:
            failed = True
        if failed:
            close_failed = False
            try:
                self.dispose()
            except p.ProtocolError:
                close_failed = True
            raise p.ProtocolError("journal_create_and_close_failed" if close_failed else "journal_create_failed") from None
        try:
            self._append({"event": "binding", "binding": asdict(binding), "limits": dict(limits),
                "kind": "document_number_attempt_journal_v1", "liveConsumable": False,
                "executionAuthorityGranted": False, "authorizationValidatedByJournal": False})
        except p.ProtocolError:
            self.dispose()
            raise

    def _append(self, value: dict[str, object]) -> None:
        p.require(not self._closed and not self._broken and self._stream is not None, "journal_unwritable")
        assert self._stream is not None
        raw = p.canonical({"sequence": self._sequence, **value})
        p.require(len(raw) <= 8192 and self._sequence <= 4096 and self._size + len(raw) <= 4 * 1024 * 1024,
                  "journal_size_exceeded")
        failed = False
        try:
            info = self._path.stat(follow_symlinks=False)
            p.require(not self._path.is_symlink() and (info.st_dev, info.st_ino) == self._identity
                      and info.st_size == self._size, "journal_drift")
            with self._path.open("rb") as existing:
                before = existing.read(4 * 1024 * 1024 + 1)
            p.require(len(before) == self._size and sha256(before).digest() == self._hash.digest(), "journal_drift")
            p.require(self._stream.write(raw) == len(raw), "journal_short_write")
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except (OSError, p.ProtocolError):
            failed = True
        if failed:
            self._broken = True
            raise p.ProtocolError("journal_write_failed")
        self._sequence += 1
        self._size += len(raw)
        self._hash.update(raw)

    def _checkpoint(self, event: str, ticket: int | None, attempt: Attempt | None) -> None:
        # The ledger constructs finite fields and holds its one ordering lock.
        with self._lock:
            if event == "stopped":
                p.require(ticket is None and attempt is None, "journal_checkpoint_invalid")
                self._append({"event": event})
            else:
                p.require(event in ("started", "finished") and type(ticket) is int and ticket >= 0
                          and type(attempt) is Attempt, "journal_checkpoint_invalid")
                assert attempt is not None
                self._append({"event": event, "ticket": ticket, "attempt": asdict(attempt)})

    def seal_cleanup(self, report: CleanupReport) -> dict[str, object]:
        """Stop sends, require no in-flight receipts, record reported cleanup.

        The closure is an attempt-log checkpoint, not a UAT/result verdict.
        Partial cleanup is persisted but raises a finite failure afterwards.
        """
        p.require(type(report) is CleanupReport, "journal_cleanup_invalid")
        report.__post_init__()
        self.ledger.abort()
        view = self.ledger.view()
        p.require(view["pending"] == 0, "journal_receipts_pending")
        ok = all(asdict(report).values())
        value: dict[str, object] = {"event": "journal_closed", "counts": view["counts"],
            "attemptCount": len(self.ledger.events), "reportedCleanup": asdict(report),
            "cleanupVerifiedByJournal": False, "reason": "closed" if ok else "cleanup_failed",
            "qualityAssessment": "Not assessed", "releaseAllowed": False}
        with self._lock:
            self._append(value)
            self._closed = True
        self.dispose()
        p.require(ok, "journal_cleanup_failed")
        return value

    def dispose(self) -> None:
        """Close only this writer. Never remove evidence or resume a broken log."""
        failed = False
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError:
                failed = True
            self._stream = None
        self._closed = True
        if failed:
            # __exit__ may run with an active provider exception. Suppress its
            # chain too, not only exceptions caught by this close operation.
            raise p.ProtocolError("journal_close_failed") from None

    def __enter__(self) -> AttemptJournal:
        p.require(not self._closed and not self._broken, "journal_unwritable")
        return self

    def __exit__(self, *_: object) -> None:
        self.dispose()
