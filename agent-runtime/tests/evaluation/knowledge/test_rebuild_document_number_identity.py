"""Synthetic identity providers only; never Docker, HTTP or inference."""
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
from threading import Event
import traceback

import httpx
import pytest

from knowledge_corpus_tools import b_model_identity_v1 as models
from knowledge_corpus_tools import local_vector_preparation as embed
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_identity as i
from tests.evaluation.knowledge import rebuild_document_number_journal as j
from tests.evaluation.knowledge import rebuild_document_number_projection as x
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.test_rebuild_document_number_projection import jar, proof


@pytest.fixture(autouse=True)
def no_real_operations(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real_operation_forbidden")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


@pytest.fixture
def draft():
    return p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))


@pytest.fixture
def pair(tmp_path, draft):
    jars, configs, proofs = [], [], []
    java = tmp_path / "java.exe"
    java.write_bytes(b"synthetic-java")
    for arm in p.ARMS:
        path = tmp_path / arm
        path.mkdir()
        archive = path / "service.jar"
        raw = jar(arm)
        archive.write_bytes(raw)
        config = path / "config"
        config.mkdir()
        for name in i._RUNTIME_CONFIG_FILES:
            (config / name).write_bytes(b"synthetic-shared-config")
        jars.append(archive)
        configs.append(config)
        proofs.append(replace(proof(draft, arm), jar_sha256=sha256(raw).hexdigest(),
                              config_sha256=sha256(b"synthetic-config").hexdigest()))
    return x.ProjectedJavaPair(draft, java, tuple(jars), tuple(configs), tuple(proofs), {})


BINDING = ReadBinding("synthetic-alias", "synthetic-index", "synthetic-uuid", "synthetic-mapping-v1")


def model_fixture(tmp_path):
    executable = tmp_path / "docker.exe"
    executable.write_bytes(b"synthetic-docker")
    packages = {name: "1.0" for name in ("FlagEmbedding", "transformers", "torch")}
    embedding = {"revision": "1" * 40, "files": {name: {"bytes": 1, "sha256": "2" * 64}
        for name in embed.MODEL_FILES}, "service": {"bytes": 1, "sha256": embed.SERVICE_SHA},
        "implementation": {"bytes": 1, "sha256": "3" * 64}, "max_length": 1024,
        "cache_provenance": "single_snapshot_predates_start", "packages": packages}
    rerank = {"revision": models._REVISION, "files": models._RERANK_HASHES,
              "serviceSha256": "4" * 64, "packages": packages}
    binding = i.ModelBinding("a" * 64, "b" * 64, sha256(p.canonical(embedding)).hexdigest(),
        executable, sha256(executable.read_bytes()).hexdigest(), "npipe:////./pipe/docker_engine")
    return binding, embedding, rerank


class Provider:
    def __init__(self, binding, embedding, rerank, *, ledger=None):
        self.binding, self.embedding, self.rerank, self.ledger = binding, embedding, rerank, ledger
        self.calls = []

    def __call__(self, command, raw):
        assert command[:3] == [str(self.binding.docker), "--host", self.binding.docker_host]
        if self.ledger is not None:
            assert self.ledger.view()["pending"] == 1  # Reservation precedes provider.
        self.calls.append((command, raw))
        is_embedding = self.binding.embedding_container_id in command
        if command[3] == "inspect":
            port = "8908" if is_embedding else "8909"
            return p.canonical({"id": self.binding.embedding_container_id if is_embedding else self.binding.rerank_container_id,
                "image": "sha256:" + "c" * 64, "started": "2026-10-04T00:00:00Z", "running": True,
                "path": "python", "args": ["-m", "uvicorn", "embedding_server:app", "--host", "0.0.0.0", "--port", port],
                "ports": {port + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]}})
        payload = json.loads(raw)
        assert payload["started"] == "2026-10-04T00:00:00Z"
        assert payload["files"] == (list(embed.MODEL_FILES) if is_embedding else sorted(models._RERANK_HASHES))
        assert command[-1] == (embed._PROBE if is_embedding else models._RERANK_PROBE)
        return p.canonical(self.embedding if is_embedding else self.rerank)


def session(monkeypatch, pair, tmp_path, *, expected=None, checkpoint=None):
    model, embedding, rerank = model_fixture(tmp_path)
    phases = ("preparation",) if expected is None else ("pre", "post")
    entries = []
    ledger = i.IdentityLedger(phases=phases, checkpoint=checkpoint or (lambda *args: entries.append(args)))
    provider = Provider(model, embedding, rerank, ledger=ledger)
    monkeypatch.setattr(i, "capture_static_identity", lambda *_: b'{"synthetic":true}\n')
    return i.IdentitySession(pair=pair, binding=BINDING, model=model, ledger=ledger,
                            process=provider, expected=expected), provider, entries


def test_existing_collector_checks_all_four_commands_before_durable_dispatch(monkeypatch, pair, tmp_path):
    value, provider, entries = session(monkeypatch, pair, tmp_path)
    capture = value.capture("preparation")
    assert value.observed == capture and value.failure_phase is None
    assert len(provider.calls) == 4 and [row[0] for row in entries] == ["started", "finished"] * 4
    assert value.ledger.view()["counts"] == {"preparation": 4}
    assert value.ledger.view()["pending"] == 0
    material = json.loads(capture.material)
    assert material["models"]["embedding"]["model"] == provider.embedding
    assert material["models"]["rerank"]["model"] == provider.rerank
    assert capture.preview()["executionAuthorityGranted"] is False
    assert "synthetic" not in repr(capture) and "tokenizer.json" not in repr(value.ledger.view())
    assert "http_status" not in repr(entries)  # Docker is not HTTP.


def test_pre_and_post_match_preparation_and_never_reuse_a_phase(monkeypatch, pair, tmp_path):
    preparation, _, _ = session(monkeypatch, pair, tmp_path)
    expected = preparation.capture("preparation")
    execution, provider, _ = session(monkeypatch, pair, tmp_path, expected=expected)
    assert execution.capture("pre") == execution.capture("post") == expected
    assert len(provider.calls) == 8
    with pytest.raises(p.ProtocolError, match="phase_invalid"):
        execution.capture("post")
    assert len(provider.calls) == 8 and execution.ledger.view()["stopped"] is True
    assert execution.failure_phase == "phase_invalid" and execution.observed is None


@pytest.mark.parametrize("phase", ["post", "pre", "unknown", "preparation/"])
def test_wrong_phase_sends_nothing(monkeypatch, pair, tmp_path, phase):
    value, provider, _ = session(monkeypatch, pair, tmp_path)
    with pytest.raises(p.ProtocolError, match="phase_invalid"):
        value.capture(phase)
    assert provider.calls == []
    assert value.failure_phase == "phase_invalid" and value.observed is None


@pytest.mark.parametrize("failure", ["start-checkpoint", "finish-checkpoint", "provider", "empty", "large", "malformed"])
def test_failure_is_finite_consumed_and_never_retries(monkeypatch, pair, tmp_path, failure):
    def writer(event, ticket, attempt):
        if event == ("started" if failure == "start-checkpoint" else "finished") and "checkpoint" in failure:
            raise OSError("private-sensitive-journal-failure")
    value, provider, _ = session(monkeypatch, pair, tmp_path, checkpoint=writer)
    original = value.process
    def fail(command, raw):
        provider.calls.append((command, raw))
        if failure == "provider":
            raise OSError("private-sensitive-provider-failure")
        if failure == "empty": return b""
        if failure == "large": return b"x" * 65537
        if failure == "malformed": return b'{"bad":"private-sensitive-output"}'
        provider.calls.pop()
        return original(command, raw)
    value.process = fail
    with pytest.raises(p.ProtocolError) as error:
        value.capture("preparation")
    assert "private-sensitive" not in "".join(traceback.format_exception(error.value))
    assert len(provider.calls) == (0 if failure == "start-checkpoint" else 1)
    assert value.ledger.view()["stopped"] is True
    with pytest.raises(p.ProtocolError, match="phase_invalid"):
        value.capture("preparation")
    assert len(provider.calls) <= 1


def test_wrong_project_environment_or_changed_executable_blocks_all_probes(monkeypatch, pair, tmp_path):
    value, provider, _ = session(monkeypatch, pair, tmp_path)
    monkeypatch.setattr(models, "_require_locked_corpus_environment", lambda: (_ for _ in ()).throw(models.BModelIdentityError()))
    with pytest.raises(p.ProtocolError, match="capture_failed"):
        value.capture("preparation")
    assert provider.calls == []


def test_executable_drift_between_commands_stops_without_second_probe(monkeypatch, pair, tmp_path):
    value, provider, _ = session(monkeypatch, pair, tmp_path)
    def mutate(command, raw):
        output = provider(command, raw)
        value.model.docker.write_bytes(b"drifted-docker")
        return output
    value.process = mutate
    with pytest.raises(p.ProtocolError, match="capture_failed"):
        value.capture("preparation")
    assert len(provider.calls) == 1


@pytest.mark.parametrize("field,new_value", [("docker_host", "tcp://127.0.0.1:2375"),
    ("embedding_container_id", "a" * 12), ("rerank_container_id", "a" * 64),
    ("docker_sha256", "x" * 64), ("docker", Path("docker"))])
def test_model_binding_does_not_discover_or_redirect_docker(tmp_path, field, new_value):
    binding, _, _ = model_fixture(tmp_path)
    with pytest.raises(p.ProtocolError, match="binding_invalid"):
        replace(binding, **{field: new_value})


def static_setup(monkeypatch, pair):
    def git(*args):
        if args[0] == "rev-parse": return pair.draft.frozen_head.encode()
        if args[0] == "status": return b""
        relative = args[1].split(":", 1)[1]
        return b"synthetic-config" if relative == x.CONFIG else (p.ROOT / relative).read_bytes()
    monkeypatch.setattr(i, "_git_bytes", git)
    monkeypatch.setattr(i, "_frozen_runtime_config_dir", lambda jar_path, head:
        (pair.configs[pair.jars.index(jar_path)],
         dict.fromkeys(i._RUNTIME_CONFIG_FILES, sha256(b"synthetic-shared-config").hexdigest())))


def test_actual_binaries_config_and_current_catalog_form_static_identity(monkeypatch, pair):
    static_setup(monkeypatch, pair)
    raw = i.capture_static_identity(pair, BINDING)
    value = json.loads(raw)
    assert value["frozenHead"] == pair.draft.frozen_head
    assert len(value["arms"]) == 2 and len(value["arms"][0]["projectionRows"]) == 11
    assert value["profiles"]["tax.law"] == BINDING.profile_snapshot("tax.law")
    assert value["catalog"]["sourceSha256"] == "87c3963a15ea98cca444438c3439094b6881bba31ceaef265db92f5caab21b00"
    assert b"synthetic-shared-config" not in raw and b"secret" not in raw


@pytest.mark.parametrize("mutation", ["jar", "proof", "shared", "java", "head", "dirty"])
def test_static_snapshot_rejects_or_detects_changes(monkeypatch, pair, mutation):
    static_setup(monkeypatch, pair)
    before = i.capture_static_identity(pair, BINDING)
    if mutation == "jar": pair.jars[0].write_bytes(b"bad")
    elif mutation == "proof": pair.proofs = (replace(pair.proofs[0], config_sha256="a" * 64), pair.proofs[1])
    elif mutation == "shared": (pair.configs[0] / "application.yml").write_bytes(b"changed")
    elif mutation == "java": pair.java.write_bytes(b"changed")
    else:
        original = i._git_bytes
        monkeypatch.setattr(i, "_git_bytes", lambda *args: b"changed" if args[0] == ("status" if mutation == "dirty" else "rev-parse")
                            else original(*args))
    if mutation == "java":
        assert i.capture_static_identity(pair, BINDING) != before
    else:
        with pytest.raises(p.ProtocolError):
            i.capture_static_identity(pair, BINDING)


@pytest.mark.parametrize("drift", ["static", "model"])
def test_pre_or_post_identity_drift_cannot_produce_success(monkeypatch, pair, tmp_path, drift):
    preparation, _, _ = session(monkeypatch, pair, tmp_path)
    expected = preparation.capture("preparation")
    execution, provider, _ = session(monkeypatch, pair, tmp_path, expected=expected)
    assert execution.capture("pre") == expected
    if drift == "static": monkeypatch.setattr(i, "capture_static_identity", lambda *_: b'{"changed":true}\n')
    else: provider.rerank = {**provider.rerank, "serviceSha256": "e" * 64}
    with pytest.raises(p.ProtocolError, match="capture_failed"):
        execution.capture("post")
    assert execution.ledger.view()["stopped"] is True
    assert len(provider.calls) == (4 if drift == "static" else 8)
    assert execution.failure_phase == ("static_identity" if drift == "static" else "expected_comparison")
    if drift == "static":
        assert execution.observed is None  # Do not expose stale successful pre identity.
    else:
        assert execution.observed is not None and execution.observed != expected
        assert execution.observed.model_sha256 != expected.model_sha256


def test_invalid_collector_has_finite_phase_without_raw_output(monkeypatch, pair, tmp_path):
    value, provider, _ = session(monkeypatch, pair, tmp_path)
    provider.rerank = {**provider.rerank, "files": {"private-sensitive-output": "bad"}}
    with pytest.raises(p.ProtocolError, match="capture_failed"):
        value.capture("preparation")
    assert len(provider.calls) == 4 and value.ledger.view()["pending"] == 0
    assert value.failure_phase == "model_capture" and value.observed is None


@pytest.mark.parametrize("stop_failure", [False, True])
def test_cancel_waits_for_worker_and_blocks_following_probe(monkeypatch, pair, tmp_path, stop_failure):
    def writer(event, ticket, attempt):
        if event == "stopped" and stop_failure: raise OSError("private-stop-failed")
    value, provider, _ = session(monkeypatch, pair, tmp_path, checkpoint=writer)
    entered, release = Event(), Event()
    def blocking(command, raw):
        entered.set()
        assert release.wait(5)
        return provider(command, raw)
    value.process = blocking
    async def run():
        task = asyncio.create_task(value.capture_async("preparation"))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(p.ProtocolError if stop_failure else asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert len(provider.calls) == 1 and value.ledger.view()["pending"] == 0
    assert value.ledger.view()["stopped"] is True


def test_concurrent_post_or_late_last_probe_cannot_overtake_pre(monkeypatch, pair, tmp_path):
    preparation, _, _ = session(monkeypatch, pair, tmp_path)
    expected = preparation.capture("preparation")
    value, provider, _ = session(monkeypatch, pair, tmp_path, expected=expected)
    def race(command, raw):
        result = provider(command, raw)
        if len(provider.calls) == 4:
            with pytest.raises(p.ProtocolError, match="phase_invalid"):
                value.capture("post")
        return result
    value.process = race
    with pytest.raises(p.ProtocolError, match="capture_failed"):
        value.capture("pre")
    assert len(provider.calls) == 4


def test_shared_durable_journal_counts_non_http_and_requires_receipts_before_seal(tmp_path):
    binding = j.JournalBinding("synthetic-document-number-008", "a" * 40, "b" * 64,
                              "c" * 64, "d" * 64, "e" * 64, "synthetic_non_live")
    with j.AttemptJournal(directory=tmp_path / binding.run_id, binding=binding,
                         limits=(("metadata", 18),), identity_phases=("pre", "post")) as journal:
        ledger = journal.identity_ledger
        assert ledger is not None
        ticket = ledger.begin("pre", 0, ["synthetic-only"], b"")
        with pytest.raises(p.ProtocolError, match="identity_receipts_pending"):
            journal.seal_cleanup(j.CleanupReport(True, True, True, True))
        ledger.finish(ticket, failed=False)
        result = journal.seal_cleanup(j.CleanupReport(True, True, True, True))
        assert result["nonHttpModelIdentityCounts"] == {"pre": 1, "post": 0}
    raw = (tmp_path / binding.run_id / "attempts.jsonl").read_bytes()
    assert b"synthetic-only" not in raw
    rows = [json.loads(line) for line in raw.splitlines()]
    assert rows[0]["nonHttpModelIdentityLimits"] == {"pre": 4, "post": 4}
    assert any(row["event"] == "model_identity_started" for row in rows)
    assert rows[-1]["reason"] == "closed" and rows[-1]["releaseAllowed"] is False
