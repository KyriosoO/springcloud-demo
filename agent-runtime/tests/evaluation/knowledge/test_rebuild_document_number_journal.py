"""Synthetic durable checkpoints only; no live run or cleanup proof is created."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess
import traceback

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_journal as j
from tests.evaluation.knowledge import rebuild_document_number_transport as t
from tests.evaluation.knowledge.test_rebuild_document_number_transport import (
    physical, request, response, synthetic_keyword_hashes,
)


@pytest.fixture(autouse=True)
def no_real_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real_resource_forbidden")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture
def binding():
    return j.JournalBinding("synthetic-document-number-001", "a" * 40,
                           "b" * 64, "c" * 64, "d" * 64, "e" * 64, "synthetic_non_live")


@pytest.fixture
def draft():
    return p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))


def journal(tmp_path, binding, limits=(("queryEmbedding", 10),)):
    return j.AttemptJournal(directory=tmp_path / binding.run_id, binding=binding, limits=limits)


def records(tmp_path, binding):
    return [json.loads(line) for line in (tmp_path / binding.run_id / "attempts.jsonl").read_bytes().splitlines()]


class BrokenStream:
    def __init__(self, wrapped, operation):
        self.wrapped, self.operation = wrapped, operation

    def write(self, raw):
        if self.operation == "short":
            return self.wrapped.write(raw[:-1])
        if self.operation == "write":
            raise OSError("private-journal-error")
        return self.wrapped.write(raw)

    def flush(self):
        if self.operation == "flush":
            raise OSError("private-journal-error")
        self.wrapped.flush()

    def fileno(self):
        return self.wrapped.fileno()

    def close(self):
        self.wrapped.close()


@pytest.mark.parametrize("field,value", [("run_id", "../escape"), ("run_id", "knowledge-b-reuse-20261003-01"),
    ("frozen_head", "a" * 39), ("protocol_sha256", "raw-body"), ("authorization_sha256", True),
    ("snapshot_sha256", "F" * 64), ("evidence_kind", "Passed"), ("evidence_kind", "live_attempts")])
def test_binding_cannot_inherit_an_old_run_or_claim_live_authority(binding, field, value, tmp_path):
    with pytest.raises(p.ProtocolError, match="binding_invalid"):
        replace(binding, **{field: value})
    assert not tuple(tmp_path.iterdir())


def test_new_header_is_exclusive_and_not_an_authorization_or_result(tmp_path, binding):
    with journal(tmp_path, binding) as log:
        header = records(tmp_path, binding)[0]
        assert header["sequence"] == 0 and header["binding"] == json.loads(p.canonical(j.asdict(binding)))
        assert header["liveConsumable"] is False and header["executionAuthorityGranted"] is False
        assert header["authorizationValidatedByJournal"] is False
        with pytest.raises(p.ProtocolError, match="create_failed"):
            journal(tmp_path, binding)
        assert log.ledger.view()["events"] == []
    assert [path.name for path in (tmp_path / binding.run_id).iterdir()] == ["attempts.jsonl"]


@pytest.mark.parametrize("wire", [b"", b'{"event":"started"', b'{"unknown":"old"}\n'])
def test_existing_even_partial_journal_is_never_reopened(tmp_path, binding, wire):
    directory = tmp_path / binding.run_id
    directory.mkdir()
    file = directory / "attempts.jsonl"
    file.write_bytes(wire)
    with pytest.raises(p.ProtocolError, match="create_failed"):
        journal(tmp_path, binding)
    assert file.read_bytes() == wire


def test_invalid_limits_or_missing_parent_fail_before_new_directory(tmp_path, binding):
    with pytest.raises(p.ProtocolError):
        journal(tmp_path, binding, (("model", 36),))
    assert not tuple(tmp_path.iterdir())
    with pytest.raises(p.ProtocolError, match="path_invalid"):
        j.AttemptJournal(directory=tmp_path / "missing" / binding.run_id, binding=binding,
                         limits=(("queryEmbedding", 10),))


@pytest.mark.parametrize("operation", ["write", "short", "flush", "fsync"])
async def test_started_must_be_durable_before_send(tmp_path, binding, draft, monkeypatch, operation):
    sent = []
    class Delegate:
        async def send(self, **kwargs):
            sent.append(kwargs)
            return response()
    with journal(tmp_path, binding) as log:
        if operation == "fsync":
            def failed_fsync(fd):
                raise OSError("private-journal-error")
            monkeypatch.setattr(j.os, "fsync", failed_fsync)
        else:
            log._stream = BrokenStream(log._stream, operation)
        port = t.CountedKnowledgeTransport(delegate=Delegate(), ledger=log.ledger,
            case=draft.cases[0], arm="shared", kind="queryEmbedding")
        with pytest.raises(p.ProtocolError, match="attempt_journal_failed") as caught:
            await port.send(request=request({"texts": [draft.cases[0].plan.original_question]}, path="/embed", token=False), timeout_s=3)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert log.ledger.counts["queryEmbedding"] == 1 and log.ledger.view()["pending"] == 1
        assert log.ledger.view()["stopped"] is True and not sent
        with pytest.raises(p.ProtocolError, match="batch_stopped"):
            log.ledger.begin("queryEmbedding", "UAT-KM-002/shared", b"other")


async def test_real_adapter_seam_sees_started_record_before_delegate(tmp_path, binding, draft):
    case = draft.cases[0]
    class Delegate:
        async def send(self, **kwargs):
            row = records(tmp_path, binding)[-1]
            assert row["event"] == "started" and row["ticket"] == 0
            assert row["attempt"]["outcome"] == "pending"
            return response()
    with journal(tmp_path, binding) as log:
        port = t.CountedKnowledgeTransport(delegate=Delegate(), ledger=log.ledger,
            case=case, arm="shared", kind="queryEmbedding")
        await port.send(request=request({"texts": [case.plan.original_question]}, path="/embed", token=False), timeout_s=3)
        closed = log.seal_cleanup(j.CleanupReport(True, True, True, True))
        assert closed["qualityAssessment"] == "Not assessed" and closed["releaseAllowed"] is False
        assert closed["cleanupVerifiedByJournal"] is False
    rows = records(tmp_path, binding)
    assert [row["event"] for row in rows] == ["binding", "started", "finished", "stopped", "journal_closed"]
    assert [row["sequence"] for row in rows] == list(range(5))
    text = (tmp_path / binding.run_id / "attempts.jsonl").read_text(encoding="utf-8")
    assert case.plan.original_question not in text and "Bearer" not in text and "queryVector" not in text


@pytest.mark.parametrize("provider", ["timeout", "cancelled", "physical"])
async def test_receipt_write_failure_has_no_raw_provider_context(tmp_path, binding, draft, monkeypatch, provider):
    with journal(tmp_path, binding, (("physicalSearch", 44),) if provider == "physical" else (("queryEmbedding", 10),)) as log:
        original = j.os.fsync
        calls = []
        def fsync(fd):
            calls.append(fd)
            if len(calls) == 2:  # started succeeds, receipt persistence fails
                raise OSError("private-receipt-error")
            original(fd)
        monkeypatch.setattr(j.os, "fsync", fsync)
        case = draft.cases[0]
        class Failed:
            async def send(self, **kwargs):
                if provider == "cancelled":
                    raise asyncio.CancelledError("private-provider-error")
                raise TimeoutError("private-provider-error")
        if provider == "physical":
            gate = t.PhysicalSearchGate(case=case, arm="old", read_alias="synthetic-read",
                vector=(0.0,) * 1024, ledger=log.ledger, keyword_sha256=synthetic_keyword_hashes(case))
            def send(body):
                raise OSError("private-provider-error")
            with pytest.raises(p.ProtocolError, match="attempt_journal_failed") as caught:
                gate.forward(method="POST", path="/synthetic-read/_search", body=p.canonical(physical(case)), send=send)
        else:
            port = t.CountedKnowledgeTransport(delegate=Failed(), ledger=log.ledger, case=case, arm="shared", kind="queryEmbedding")
            with pytest.raises(p.ProtocolError, match="attempt_journal_failed") as caught:
                await port.send(request=request({"texts": [case.plan.original_question]}, path="/embed", token=False), timeout_s=3)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert log.ledger.view()["pending"] == 1 and log.ledger.view()["stopped"] is True
        assert log.ledger.events[0].outcome == "pending"
        assert "private-provider-error" not in (tmp_path / binding.run_id / "attempts.jsonl").read_text(encoding="utf-8")


async def test_cancellation_has_durable_receipt_and_no_retry(tmp_path, binding, draft):
    class Cancelled:
        async def send(self, **kwargs):
            raise asyncio.CancelledError("private")
    with journal(tmp_path, binding) as log:
        port = t.CountedKnowledgeTransport(delegate=Cancelled(), ledger=log.ledger, case=draft.cases[0], arm="shared", kind="queryEmbedding")
        with pytest.raises(asyncio.CancelledError) as caught:
            await port.send(request=request({"texts": [draft.cases[0].plan.original_question]}, path="/embed", token=False), timeout_s=3)
        assert caught.value.__context__ is None
        assert records(tmp_path, binding)[-1]["attempt"]["outcome"] == "cancelled"
        assert log.ledger.view()["pending"] == 0 and log.ledger.view()["stopped"] is True


@pytest.mark.parametrize("mutation", ["same_size", "append", "replace"])
def test_external_log_drift_stops_next_send(tmp_path, binding, mutation):
    with journal(tmp_path, binding) as log:
        path = tmp_path / binding.run_id / "attempts.jsonl"
        raw = path.read_bytes()
        if mutation == "same_size":
            path.write_bytes(raw.replace(b'"binding"', b'"changed"', 1))
        elif mutation == "append":
            with path.open("ab") as stream:
                stream.write(b"extra")
        else:
            replacement = path.with_name("replacement")
            replacement.write_bytes(raw)
            # The owned Windows handle prevents replacement while open; treat
            # this as a changed stat identity without actually replacing it.
            log._identity = (-1, -1)
        with pytest.raises(p.ProtocolError, match="attempt_journal_failed"):
            log.ledger.begin("queryEmbedding", "UAT-KM-001/shared", b"private-body")
        assert log.ledger.view()["stopped"] is True


def test_parallel_checkpoints_have_one_sequence_and_unique_tickets(tmp_path, binding):
    with journal(tmp_path, binding, (("metadata", 16),)) as log:
        def invoke(number):
            ticket = log.ledger.begin("metadata", f"probe/{number}", b"private-body")
            log.ledger.finish(ticket, "completed", 200)
            return ticket
        with ThreadPoolExecutor(max_workers=4) as pool:
            tickets = list(pool.map(invoke, range(16)))
        assert sorted(tickets) == list(range(16))
        log.seal_cleanup(j.CleanupReport(True, True, True, True))
        rows = records(tmp_path, binding)
        assert [row["sequence"] for row in rows] == list(range(len(rows)))
        for ticket in tickets:
            events = [row["event"] for row in rows if row.get("ticket") == ticket]
            assert events == ["started", "finished"]
        assert "private-body" not in json.dumps(rows)


def test_pending_receipts_cannot_be_sealed_or_declared_cleanup_complete(tmp_path, binding):
    with journal(tmp_path, binding) as log:
        ticket = log.ledger.begin("queryEmbedding", "UAT-KM-001/shared", b"private-body")
        with pytest.raises(p.ProtocolError, match="receipts_pending"):
            log.seal_cleanup(j.CleanupReport(True, True, True, True))
        assert records(tmp_path, binding)[-1]["event"] == "stopped"
        log.ledger.finish(ticket, "cancelled")
        log.seal_cleanup(j.CleanupReport(True, True, True, True))


def test_cleanup_failure_is_preserved_and_not_reported_as_verified(tmp_path, binding):
    with journal(tmp_path, binding) as log:
        with pytest.raises(p.ProtocolError, match="cleanup_failed"):
            log.seal_cleanup(j.CleanupReport(True, False, True, True))
        closed = records(tmp_path, binding)[-1]
        assert closed["reason"] == "cleanup_failed" and closed["reportedCleanup"]["clients_closed"] is False
        assert closed["cleanupVerifiedByJournal"] is False and closed["qualityAssessment"] == "Not assessed"
        with pytest.raises(p.ProtocolError, match="batch_stopped"):
            log.ledger.begin("queryEmbedding", "UAT-KM-001/shared", b"private-body")


def test_closed_handle_or_unknown_cleanup_cannot_create_success(tmp_path, binding):
    log = journal(tmp_path, binding)
    log.dispose()
    with pytest.raises(p.ProtocolError, match="attempt_journal_failed"):
        log.ledger.begin("queryEmbedding", "UAT-KM-001/shared", b"private-body")
    assert not any(row["event"] == "journal_closed" for row in records(tmp_path, binding))
    with pytest.raises(p.ProtocolError, match="cleanup_invalid"):
        j.CleanupReport(True, 1, True, True)


def test_header_fsync_failure_is_finite_and_new_directory_cannot_resume(tmp_path, binding, monkeypatch):
    def failed(fd):
        raise OSError("private-header-error")
    monkeypatch.setattr(j.os, "fsync", failed)
    with pytest.raises(p.ProtocolError, match="journal_write_failed") as caught:
        journal(tmp_path, binding)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    with pytest.raises(p.ProtocolError, match="create_failed"):
        journal(tmp_path, binding)


@pytest.mark.parametrize("close_fails", [False, True])
def test_fstat_failure_closes_owned_handle_and_preserves_failure_directory(tmp_path, binding, monkeypatch, close_fails):
    opened = []
    original_open = Path.open
    class CloseFailure(BrokenStream):
        def close(self):
            self.wrapped.close()
            raise OSError("private-close-error")
    def open_file(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if mode == "xb":
            opened.append(stream)
            return CloseFailure(stream, None) if close_fails else stream
        return stream
    def fstat(fd):
        raise OSError("private-fstat-error")
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(j.os, "fstat", fstat)
    with pytest.raises(p.ProtocolError, match="journal_create_.*failed") as caught:
        journal(tmp_path, binding)
    assert len(opened) == 1 and opened[0].closed is True
    assert caught.value.__suppress_context__ is True
    assert "private-fstat-error" not in "".join(traceback.format_exception(caught.value))
    assert "private-close-error" not in "".join(traceback.format_exception(caught.value))
    assert (tmp_path / binding.run_id / "attempts.jsonl").exists()
    with pytest.raises(p.ProtocolError, match="create_failed"):
        journal(tmp_path, binding)


def test_provider_and_close_double_failure_suppresses_raw_traceback(tmp_path, binding):
    class CloseFailure(BrokenStream):
        def close(self):
            self.wrapped.close()
            raise OSError("private-close-error")
    log = journal(tmp_path, binding)
    owned = log._stream
    log._stream = CloseFailure(owned, None)
    with pytest.raises(p.ProtocolError, match="journal_close_failed") as caught:
        with log:
            raise RuntimeError("private-provider-body")
    assert owned.closed is True and caught.value.__suppress_context__ is True
    formatted = "".join(traceback.format_exception(caught.value))
    assert "private-provider-body" not in formatted and "private-close-error" not in formatted
    assert log._stream is None
