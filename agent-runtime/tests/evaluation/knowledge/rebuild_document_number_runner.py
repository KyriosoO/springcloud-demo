"""Private serial preparation/execution boundary, not a CLI or grant issuer.

A trusted caller must verify a NEW exact human decision before supplying its
receipt. This module checks consistency, never the human provenance itself.
There is no default confirmer, process provider, run, HTTP client or live grant.
Synthetic tests cannot be promoted by changing an output directory.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import os
from pathlib import Path
import re
from threading import Lock
import time
from typing import TypeVar, cast

import httpx

from agent_runtime.capability_api.contracts import CancellationSignal
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_identity import (
    IdentityCapture, IdentitySession, ModelBinding, Process, capture_static_identity,
)
from tests.evaluation.knowledge.rebuild_document_number_inventory import (
    InventoryCapture, InventorySession, exact_http_limits,
)
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, CleanupReport, JournalBinding
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_projection import ProjectedJavaPair
from tests.evaluation.knowledge.rebuild_document_number_runtime import OwnedComparisonCapture, OwnedComparisonRuntime

_ROOT = p.ROOT / "agent-runtime/tests/uat/results/document-number-comparison"
_T = TypeVar("_T")


def _digest(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True)
class RunScope:
    """Technical operation scope. Its bytes/hash do not grant permission."""
    run_id: str
    reference: str
    phase: str
    evidence_kind: str
    not_before: int
    expires_at: int
    pair: ProjectedJavaPair = field(repr=False)
    binding: ReadBinding
    model: ModelBinding
    mapping_sha256: str
    static_sha256: str
    record_count: int
    ports: tuple[int, int, int, int]
    inventory: InventoryCapture | None = field(default=None, repr=False)
    identity: IdentityCapture | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        p.require(self.phase in ("preparation", "execution") and type(self.pair) is ProjectedJavaPair
            and type(self.binding) is ReadBinding and type(self.model) is ModelBinding
            and _digest(self.mapping_sha256) and _digest(self.static_sha256) and type(self.reference) is str
            and re.fullmatch(r"[A-Za-z0-9_:./-]{1,160}", self.reference) is not None
            and type(self.not_before) is int and type(self.expires_at) is int
            and 0 < self.not_before < self.expires_at < 2**53
            and type(self.ports) is tuple and len(self.ports) == 4 and len(set(self.ports)) == 4
            and all(type(port) is int and 1024 <= port <= 65535 and port not in (9200, 8908, 8909)
                    for port in self.ports), "runner_scope_invalid")
        self.pair.draft.__post_init__()
        self.binding.__post_init__()
        self.model.__post_init__()
        exact_http_limits(self.record_count, include_preparation=False)
        self.journal_binding("0" * 64).__post_init__()
        p.require((self.phase == "preparation" and self.inventory is None and self.identity is None)
            or (self.phase == "execution" and type(self.inventory) is InventoryCapture
                and type(self.identity) is IdentityCapture), "runner_snapshot_required")
        if self.inventory is not None:
            p.require(self.inventory.binding == self.binding and self.inventory.record_count == self.record_count
                and self.inventory.mapping_sha256 == self.mapping_sha256
                and sha256(self.inventory.inventory).hexdigest() == self.inventory.inventory_sha256
                and _digest(self.inventory.source_fingerprint), "runner_inventory_invalid")
        if self.identity is not None:
            p.require(_digest(self.identity.static_sha256) and _digest(self.identity.model_sha256)
                and _digest(self.identity.identity_sha256) and type(self.identity.material) is bytes
                and 0 < len(self.identity.material) <= 65536
                and sha256(self.identity.material).hexdigest() == self.identity.identity_sha256,
                "runner_identity_invalid")

    def limits(self) -> tuple[tuple[str, int], ...]:
        rows = dict(exact_http_limits(self.record_count, include_preparation=False))
        if self.phase == "preparation":
            rows = dict.fromkeys(rows, 0)
            rows["snapshotPreparation"] = 1 + (self.record_count + 249) // 250
            rows["preparationMetadata"] = 3
        return tuple(rows.items())

    def journal_binding(self, authorization_sha256: str) -> JournalBinding:
        return JournalBinding(self.run_id, self.pair.draft.frozen_head,
            sha256(p.canonical(self.pair.draft.preview())).hexdigest(),
            sha256(p.canonical([asdict(proof) for proof in self.pair.proofs])).hexdigest(),
            sha256(p.canonical({"inventory": None if self.inventory is None else self.inventory.preview(),
                "identity": None if self.identity is None else self.identity.preview()})).hexdigest(),
            authorization_sha256, self.evidence_kind)

    def material(self) -> bytes:
        model = asdict(self.model)
        model["docker"] = str(self.model.docker)
        return p.canonical({"kind": "document_number_independent_scope_v1", "runId": self.run_id,
            "reference": self.reference, "phase": self.phase, "evidenceKind": self.evidence_kind,
            "window": {"notBefore": self.not_before, "expiresAt": self.expires_at},
            "exclusiveWindowRequired": True, "binding": asdict(self.journal_binding("0" * 64)),
            "staticSha256": self.static_sha256,
            "target": {"esOrigin": "http://127.0.0.1:9200", **asdict(self.binding)},
            "models": model, "ports": list(self.ports), "httpLimits": dict(self.limits()),
            "modelIdentityProcessLimit": 4 if self.phase == "preparation" else 8,
            "serviceStartsAndOwnedStops": 0 if self.phase == "preparation" else 2,
            "forbidden": dict.fromkeys(p.FORBIDDEN, 0), "humanProvenanceVerifiedByThisModule": False})


@dataclass(frozen=True, slots=True)
class ConfirmationReceipt:
    """Receipt from a TRUSTED human-decision boundary, not a local approval.

    The caller owns actual provenance/exclusive-window verification. A callback
    manufacturing this object is not evidence of a real user decision. Tests
    supply synthetic receipts only; there is no production confirmer here.
    """
    authorization_sha256: str
    reference: str
    decision_record_sha256: str


Confirm = Callable[[bytes], ConfirmationReceipt]
ClientFactory = Callable[[], httpx.Client]


def _close_client(client: httpx.Client) -> bool:
    client.close()
    return client.is_closed


def _stop(journal: AttemptJournal) -> bool:
    ok = True
    for ledger in (journal.ledger, journal.identity_ledger):
        if ledger is not None:
            try:
                ledger.abort()
            except Exception:
                ok = False  # The other category and worker cleanup must still run.
    return ok


async def _guarded(call: Callable[[], Awaitable[_T]], signal: CancellationSignal,
                   journal: AttemptJournal) -> _T:
    if signal.is_cancelled():
        _stop(journal)
        raise asyncio.CancelledError
    async def invoke() -> _T:
        return await call()
    work = asyncio.create_task(invoke())
    watcher = asyncio.create_task(signal.wait_cancelled())
    failed = cancelled = False
    result: _T | None = None
    try:
        await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
        if watcher.done() or signal.is_cancelled():
            raise asyncio.CancelledError
        result = work.result()
    except asyncio.CancelledError:
        cancelled = True
    except Exception:
        failed = True
    finally:
        if failed or cancelled:
            failed = not _stop(journal) or failed
        for task in (work, watcher):
            if not task.done():
                task.cancel()
        # capture_async drains its thread; repeated outer cancellation cannot
        # abandon that drain or close the inventory client underneath it.
        drain = asyncio.gather(work, watcher, return_exceptions=True)
        while not drain.done():
            try:
                await asyncio.shield(drain)
            except asyncio.CancelledError:
                cancelled = True
                failed = not _stop(journal) or failed
        drain.result()
    if failed:
        raise p.ProtocolError("runner_phase_failed") from None
    if cancelled:
        raise asyncio.CancelledError from None
    return cast(_T, result)  # None is a valid postcheck return.


def _directory(path: Path) -> None:
    p.require(path.is_absolute() and path.resolve() == path.absolute() and not path.is_symlink(),
              "runner_path_invalid")
    path.mkdir(parents=True, exist_ok=True)
    p.require(path.is_dir() and path.resolve() == path.absolute(), "runner_path_invalid")


def _consume(root: Path, scope: RunScope, raw: bytes, receipt: ConfirmationReceipt) -> Path:
    _directory(root)
    claims, runs = root / "consumed", root / "runs"
    _directory(claims)
    _directory(runs)
    directory = runs / scope.run_id
    p.require(not directory.exists() and not directory.is_symlink(), "runner_run_exists")
    marker = claims / (scope.run_id + ".json")
    value = p.canonical({"kind": "document_number_consumed_v1", "runId": scope.run_id,
        "phase": scope.phase, "authorizationSha256": sha256(raw).hexdigest(),
        "decisionRecordSha256": receipt.decision_record_sha256, "reference": receipt.reference,
        "frozenHead": scope.pair.draft.frozen_head, "retry": False, "resume": False})
    failed = False
    try:
        # Exclusive creation is the one-shot claim. Even a short write/fsync
        # failure leaves it consumed. Never delete, truncate or retry it.
        with marker.open("xb") as stream:
            if stream.write(value) != len(value):
                failed = True
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        failed = True
    p.require(not failed, "runner_consume_failed")
    return directory


@dataclass(frozen=True, slots=True)
class RunCapture:
    inventory: InventoryCapture = field(repr=False)
    identity: IdentityCapture = field(repr=False)
    comparison: OwnedComparisonCapture | None
    quality_assessment: str = "Not assessed"
    release_allowed: bool = False


class IndependentRunner:
    """Consume, successful prechecks, owned runtime/postchecks, then closure.

    Only synthetic runs accept an alternate root. Live scope always uses the
    fixed repository root, including a separate preparation run/confirmation.
    The client factory must create a fresh owned client, never a borrowed one.
    """
    def __init__(self, *, scope: RunScope, authorization: bytes, confirm: Confirm,
                 process: Process, client: ClientFactory, synthetic_root: Path | None = None) -> None:
        p.require(type(scope) is RunScope and type(authorization) is bytes and callable(confirm)
            and callable(process) and callable(client), "runner_input_invalid")
        scope.__post_init__()
        p.require(authorization == scope.material(), "runner_authorization_mismatch")
        p.require(synthetic_root is None or scope.evidence_kind == "synthetic_non_live",
                  "runner_live_root_fixed")
        self.scope, self.authorization, self.confirm = scope, authorization, confirm
        self.process, self.client_factory = process, client
        self.root = _ROOT if synthetic_root is None else synthetic_root
        self._attempted = False
        self._lock = Lock()
        self.identity_failure_phase: str | None = None
        self.identity_failure_capture: IdentityCapture | None = None
        self.failure_phase: str | None = None
        # Only the owning finally block's cleanup outcome. A stop/checkpoint
        # failure inside a guarded phase remains that phase's primary failure.
        self.final_cleanup_failed = False

    def _window(self) -> None:
        p.require(self.scope.not_before <= time.time() < self.scope.expires_at, "runner_window_invalid")

    def _operation(self, cancellation: CancellationSignal) -> None:
        self._window()
        p.require(not cancellation.is_cancelled(), "runner_cancelled")
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None  # Synchronous ES/Docker workers have no event loop.
        p.require(task is None or task.cancelling() == 0, "runner_cancelled")

    async def evaluate(self, *, cancellation: CancellationSignal) -> RunCapture:
        with self._lock:
            p.require(not self._attempted, "runner_already_attempted")
            self._attempted = True
        journal: AttemptJournal | None = None
        client: httpx.Client | None = None
        result: RunCapture | None = None
        failed = cancelled = False
        stage = "entry_validation"
        try:
            if cancellation.is_cancelled():
                raise asyncio.CancelledError
            self._window()
            self.scope.__post_init__()
            p.require(self.authorization == self.scope.material(), "runner_authorization_drift")
            p.require(self.scope.evidence_kind == "synthetic_non_live" or self.root == _ROOT,
                      "runner_live_root_fixed")
            # No restricted provider has been called yet. Human provenance is
            # verified by this explicit trusted caller, NOT by an approved flag.
            stage = "confirmation"
            receipt = self.confirm(self.authorization)
            p.require(type(receipt) is ConfirmationReceipt
                and receipt.authorization_sha256 == sha256(self.authorization).hexdigest()
                and receipt.reference == self.scope.reference and _digest(receipt.decision_record_sha256),
                "runner_confirmation_invalid")
            self._window()
            if cancellation.is_cancelled():
                raise asyncio.CancelledError
            stage = "static_precheck"
            # capture_static_identity owns the leased artifact verification.
            p.require(sha256(capture_static_identity(self.scope.pair, self.scope.binding)).hexdigest()
                == self.scope.static_sha256, "runner_static_drift")
            stage = "consume"
            directory = _consume(self.root, self.scope, self.authorization, receipt)
            phases = ("preparation",) if self.scope.phase == "preparation" else ("pre", "post")
            stage = "journal_create"
            journal = AttemptJournal(directory=directory,
                binding=self.scope.journal_binding(sha256(self.authorization).hexdigest()),
                limits=self.scope.limits(), identity_phases=phases,
                operation_guard=lambda: self._operation(cancellation))
            stage = "client_create"
            created = self.client_factory()  # Opening a client performs no HTTP.
            # Take ownership before exact-type rejection, so a recognisable
            # but unsupported subclass does not leak its returned handle.
            if isinstance(created, httpx.Client):
                client = created
            p.require(type(client) is httpx.Client and not client.is_closed, "runner_client_invalid")
            assert journal.identity_ledger is not None
            stage = "session_create"
            inventories = InventorySession(draft=self.scope.pair.draft, binding=self.scope.binding,
                mapping_sha256=self.scope.mapping_sha256, record_count=self.scope.record_count,
                ledger=journal.ledger, client=client, expected=self.scope.inventory)
            identities = IdentitySession(pair=self.scope.pair, binding=self.scope.binding,
                model=self.scope.model, ledger=journal.identity_ledger, process=self.process,
                expected=self.scope.identity)

            async def phase(name: str) -> tuple[InventoryCapture, IdentityCapture]:
                nonlocal stage
                previous_stage = stage
                stage = name + "_identity"
                self._window()
                try:
                    identity = await _guarded(lambda: identities.capture_async(name), cancellation, journal)
                except Exception:
                    self.identity_failure_phase = identities.failure_phase
                    self.identity_failure_capture = identities.observed
                    raise
                p.require(identity.static_sha256 == self.scope.static_sha256, "runner_static_drift")
                stage = name + "_inventory"
                self._window()
                inventory = await _guarded(lambda: inventories.capture_async(name), cancellation, journal)
                stage = previous_stage
                return inventory, identity

            inventory, identity = await phase(phases[0])
            if self.scope.phase == "preparation":
                result = RunCapture(inventory, identity, None)
            else:
                self._window()
                async def postcheck() -> None:
                    # Both sessions compare every successful capture with the
                    # same frozen expected snapshot. Keep the actual postflight,
                    # not a second equality check of already validated values.
                    await phase("post")
                stage = "runtime"
                runtime = OwnedComparisonRuntime(pair=self.scope.pair, journal=journal,
                    binding=self.scope.binding, ports=self.scope.ports,
                    metadata_sha256=inventory.metadata_sha256, postcheck=postcheck, inventory_client=client)
                comparison = await _guarded(lambda: runtime.evaluate(cancellation=cancellation), cancellation, journal)
                result = RunCapture(inventory, identity, comparison)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            failed = True
            self.failure_phase = stage
        finally:
            if journal is not None:
                self.final_cleanup_failed = not _stop(journal)
            if client is not None and not client.is_closed:
                try:
                    closed = _close_client(client)
                    self.final_cleanup_failed = not closed or self.final_cleanup_failed
                except Exception:
                    self.final_cleanup_failed = True
            if journal is not None:
                try:
                    if not journal.closed:
                        journal.seal_cleanup(CleanupReport(self.scope.pair.resources_released,
                            True if client is None else client.is_closed, self.scope.pair.resources_released,
                            self.scope.pair.resources_released))
                except Exception:
                    self.final_cleanup_failed = True
                finally:
                    try:
                        journal.dispose()
                    except Exception:
                        self.final_cleanup_failed = True
            if self.final_cleanup_failed:
                failed = True
                if self.failure_phase is None:
                    self.failure_phase = "cleanup"
        if failed:
            raise p.ProtocolError("runner_attempt_failed") from None
        if cancelled:
            raise asyncio.CancelledError from None
        assert result is not None
        return result
