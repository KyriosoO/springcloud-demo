"""Private counted inventory checks; no CLI, default client or execution grant.

The caller must independently authorize each real preparation/execution window.
This module cannot authorize ES reads or turn caller-supplied hashes into proof.
It reuses the full-record scanner; tests use only in-memory HTTP providers.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
import json
from threading import Lock
from typing import Any

import httpx

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_proxy import _backend_response, metadata_paths
from tests.evaluation.knowledge.rebuild_document_number_transport import AttemptLedger, BudgetPlan


@dataclass(frozen=True, slots=True)
class InventoryCapture:
    binding: ReadBinding
    mapping_sha256: str
    record_count: int
    source_fingerprint: str
    inventory_sha256: str
    metadata_sha256: tuple[tuple[str, str], ...]
    # Finite IDs/body hashes only, never full source records or float vectors.
    inventory: bytes = field(repr=False)

    def preview(self) -> dict[str, object]:
        return {"kind": "document_number_inventory_capture_v1", "recordCount": self.record_count,
            "sourceFingerprint": self.source_fingerprint, "inventorySha256": self.inventory_sha256,
            "mappingSha256": self.mapping_sha256, "metadataSha256": dict(self.metadata_sha256),
            "executionAuthorityGranted": False, "qualityAssessment": "Not assessed"}


def exact_http_limits(record_count: int, *, include_preparation: bool) -> tuple[tuple[str, int], ...]:
    """Current one-health-per-arm call graph; not measured counts or a grant.

    Model/PID/file inspection is not HTTP and must be separately bound by the
    outer executor. No unimplemented BGE health call is silently budgeted here.
    """
    p.require(type(include_preparation) is bool, "inventory_budget_invalid")
    rows = dict(BudgetPlan(record_count, int(include_preparation)).rows())
    rows["javaHealth"], rows["bgeHealth"] = 2, 0
    return tuple(rows.items())


class _ScanAttempts:
    def __init__(self, ledger: AttemptLedger, phase: str, index_name: str) -> None:
        self.ledger, self.phase, self.index_name = ledger, phase, index_name
        self.ordinal = 0

    def begin(self, method: str, path: str, body: bytes) -> int:
        p.require((method == "GET" and path == f"/{self.index_name}" and self.ordinal == 0 and not body)
            or (method == "POST" and path == f"/{self.index_name}/_search" and self.ordinal > 0),
            "inventory_scan_route_invalid")
        kind = "snapshotPreparation" if self.phase == "preparation" else "snapshotPrePost"
        ticket = self.ledger.begin(kind, f"inventory/{self.phase}/{self.ordinal}", body)
        self.ordinal += 1
        return ticket

    def finish(self, ticket: int, status: int | None, failed: bool) -> None:
        self.ledger.finish(ticket, "transport_failed" if status is None else "completed", status)
        if failed:
            self.ledger.abort()

    def abort(self) -> None:
        self.ledger.abort()


class InventorySession:
    """Preparation or ordered pre/post checks on the SAME client and ledger.

    A capture is obtained here, never reconstructed from a historical file.
    Equality means observed invariants, not a proof of an exclusive window or
    permission. Preparation and execution grants remain externally governed.
    This object borrows the client; it neither creates nor closes it.
    """
    def __init__(self, *, draft: p.DraftProtocol, binding: ReadBinding,
                 mapping_sha256: str, record_count: int, ledger: AttemptLedger,
                 client: httpx.Client, expected: InventoryCapture | None = None) -> None:
        import re
        p.require(type(draft) is p.DraftProtocol and type(binding) is ReadBinding
            and type(ledger) is AttemptLedger and type(mapping_sha256) is str
            and re.fullmatch(r"[0-9a-f]{64}", mapping_sha256) is not None, "inventory_binding_invalid")
        draft.__post_init__()
        BudgetPlan(record_count)
        p.require(expected is None or type(expected) is InventoryCapture
            and expected.binding == binding and expected.mapping_sha256 == mapping_sha256
            and expected.record_count == record_count
            and sha256(expected.inventory).hexdigest() == expected.inventory_sha256,
            "inventory_expected_invalid")
        self.draft, self.binding, self.mapping_sha256 = draft, binding, mapping_sha256
        self.record_count, self.ledger, self.client, self.expected = record_count, ledger, client, expected
        self.phases: list[str] = []
        self._completed: list[str] = []
        self._active = False
        self._rejected = False
        self._phase_lock = Lock()

    def _metadata(self, phase: str) -> tuple[tuple[str, str], ...]:
        values: list[dict[str, Any]] = []
        digests: list[tuple[str, str]] = []
        kind = "preparationMetadata" if phase == "preparation" else "metadata"
        for ordinal, path in enumerate(metadata_paths(self.binding)):
            ticket = self.ledger.begin(kind, f"inventory/{phase}/metadata/{ordinal}", b"")
            response = None
            failed = False
            try:
                response = _backend_response(self.client, "GET", path, b"")
            except Exception:
                failed = True
            self.ledger.finish(ticket, "transport_failed" if failed or response is None else "completed",
                None if failed or response is None else response.status_code)
            p.require(not failed and response is not None and response.status_code == 200,
                      "inventory_metadata_http_failed")
            assert response is not None
            value = p._decode(response.body)
            values.append(value)
            digests.append((path, sha256(p.canonical(value)).hexdigest()))
        alias, settings, mapping = values
        name = self.binding.index_name
        p.require(all(set(value) == {name} and type(value[name]) is dict for value in values),
                  "inventory_metadata_scope_invalid")
        aliases = alias[name].get("aliases")
        p.require(type(aliases) is dict and set(aliases) == {self.binding.read_alias}, "inventory_alias_invalid")
        flags = aliases[self.binding.read_alias]
        p.require(type(flags) is dict and set(flags) <= {"is_write_index", "is_hidden"}
            and all(type(value) is bool for value in flags.values())
            and flags.get("is_write_index", False) is False, "inventory_alias_flags_invalid")
        settings_body = settings[name].get("settings")
        p.require(type(settings_body) is dict and type(settings_body.get("index")) is dict,
                  "inventory_settings_invalid")
        index = settings_body["index"]
        p.require(index.get("uuid") == self.binding.index_uuid, "inventory_uuid_drift")
        blocks = index.get("blocks", {})
        p.require(type(blocks) is dict, "inventory_write_block_invalid")
        write = [value for value in (blocks.get("write"), index.get("blocks.write")) if value is not None]
        p.require(bool(write) and all(value is True or type(value) is str and value == "true" for value in write),
                  "inventory_write_block_invalid")
        fields = mapping[name].get("mappings")
        p.require(type(fields) is dict and type(fields.get("_meta")) is dict
            and fields["_meta"].get("mapping_version") == self.binding.mapping_version
            and sha256(p.canonical(fields)).hexdigest() == self.mapping_sha256, "inventory_mapping_drift")
        return tuple(digests)

    def capture(self, phase: str) -> InventoryCapture:
        with self._phase_lock:
            preparation = self.expected is None and phase == "preparation" and not self.phases
            execution = self.expected is not None and ((phase == "pre" and not self.phases)
                or (phase == "post" and self.phases == self._completed == ["pre"]))
            valid = not self._active and not self._rejected and (preparation or execution)
            if valid:
                self.phases.append(phase)  # Any attempted phase is one-shot, including failure.
                self._active = True
            else:
                self._rejected = True
        if not valid:
            self.ledger.abort()
            raise p.ProtocolError("inventory_phase_invalid")
        result: InventoryCapture | None = None
        failed = False
        try:
            # Loaded only by an authorized inventory path. Avoid pulling the
            # offline parser dependencies into the production Stage imports.
            from knowledge_corpus_tools.document_number_snapshot_v1 import FreshSnapshotSpec, scan_fresh_snapshot
            p.require(str(self.client.base_url).rstrip("/") == "http://127.0.0.1:9200",
                      "inventory_origin_invalid")
            metadata = self._metadata(phase)
            scan = scan_fresh_snapshot(FreshSnapshotSpec(self.binding.index_name, self.binding.index_uuid,
                self.mapping_sha256, self.record_count, 1 + (self.record_count + 249) // 250),
                client=self.client, attempts=_ScanAttempts(self.ledger, phase, self.binding.index_name))
            p.require(scan.mapping_version == self.binding.mapping_version, "inventory_mapping_drift")
            # Scanner guarantees exact all-record enumeration and content hashes;
            # independently require every fixed necessary source, without gold
            # injection into any online query or ranking.
            # This is locally constructed canonical scanner output (up to
            # 16 MiB), not a typed HTTP DTO with the separate 2 MiB limit.
            rows = json.loads(scan.raw)["records"]
            available = {(row["documentId"], row["chunkId"], row["contentSha256"]) for row in rows}
            p.require(all((ref.document_id, ref.chunk_id, ref.content_sha256) in available
                          for case in self.draft.cases for ref in case.necessary_sources),
                      "inventory_necessary_source_missing")
            result = InventoryCapture(self.binding, self.mapping_sha256, scan.record_count,
                scan.source_fingerprint, scan.sha256, metadata, scan.raw)
            p.require(self.expected is None or result == self.expected, "inventory_full_pool_drift")
        except Exception:
            failed = True
        with self._phase_lock:
            ledger_state = self.ledger.view()
            failed = failed or self._rejected or bool(ledger_state["stopped"]) or ledger_state["pending"] != 0
            self._active = False
            if not failed:
                self._completed.append(phase)
        if failed:
            self.ledger.abort()
            raise p.ProtocolError("inventory_capture_failed") from None
        assert result is not None
        return result

    async def capture_async(self, phase: str) -> InventoryCapture:
        """Join the borrowed synchronous scanner on cancellation, then fail.

        Cancelling to_thread alone does not stop its worker. Stop new ledger
        sends and wait for the current bounded request before owned cleanup.
        """
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            self.ledger.abort()
            raise asyncio.CancelledError
        task = asyncio.create_task(asyncio.to_thread(self.capture, phase))
        cancelled = False
        stop_failed = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
                try:
                    self.ledger.abort()
                except Exception:
                    # A failed stop checkpoint still stops new ledger sends.
                    # Do not abandon the thread or close its borrowed client.
                    stop_failed = True
            except Exception:
                break
        if cancelled:
            # Retrieve the worker's finite failure, but do not accept its late
            # capture after cancellation or leave an unobserved exception.
            if not task.cancelled():
                task.exception()
            if stop_failed:
                raise p.ProtocolError("inventory_cancel_stop_failed") from None
            raise asyncio.CancelledError from None
        return task.result()
