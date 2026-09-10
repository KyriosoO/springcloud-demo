"""Non-live checks for DR-KRET-036; no model cache or external calls."""
from __future__ import annotations

import contextlib
import io
import json
import sys
from types import SimpleNamespace

import pytest

from tests.system_e2e import knowledge_rerank_window_probe_v1 as probe
from tests.system_e2e import knowledge_rerank_window_worker_v1 as worker


def payload():
    return {"cases": [{"caseId": c, "query": "synthetic", "documents": ["x" * 1100] * 20}
                      for c in worker.CASES]}


def events():
    result = [{"event": "ready", "pid": 123, "modelHashes": worker.HASHES,
               "torchVersion": "test", "dtype": "float16", "device": "cuda:0"},
              {"event": "warmup", "warmupForwards": 2}]
    for n, c in enumerate(worker.CASES):
        for w in ((512, 1024) if n % 2 == 0 else (1024, 512)):
            result.append({"event": "arm", "caseId": c, "window": w,
                           "scores": [0.5] * 20, "tokens": [w] * 20,
                           "durationMs": 100, "peakAllocatedBytes": 1000, "forwards": 10})
    result.append({"event": "complete", "forwards": 80, "warmupForwards": 2})
    return result


def encode(items):
    return b"\n".join(json.dumps(x).encode() for x in items)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra="forbidden"),
    lambda p: p["cases"].pop(),
    lambda p: p["cases"][0].update(caseId="KRB-024"),
    lambda p: p["cases"][0].update(query=""),
    lambda p: p["cases"][0].update(documents=["x"] * 21),
    lambda p: p["cases"][0]["documents"].__setitem__(0, "x" * 4701),
])
def test_input_rejects_unbound_or_unbounded_values(mutation):
    value = payload()
    mutation(value)
    with pytest.raises(worker.ProbeError, match="invalid_input"):
        worker.validate_input(value)


class Tokenizer:
    def __call__(self, text, **kwargs):
        return {"input_ids": list(range(min(len(text), kwargs.get("max_length", len(text)))))}

    def prepare_for_model(self, query, document, **kwargs):
        assert kwargs["truncation"] == "only_second" and kwargs["padding"] is False
        return {"input_ids": [0] + query + [2, 2] + document[:kwargs["max_length"] - len(query) - 4] + [2]}


def test_pair_token_bound_and_query_is_unchanged():
    tokenizer = Tokenizer()
    for w in (512, 1024):
        value = worker.prepare(tokenizer, "query", ["x" * 1500, "short"], w)
        assert len(value[0]["input_ids"]) == w
        assert len(value[1]["input_ids"]) == 14
    with pytest.raises(worker.ProbeError, match="query_truncated"):
        worker.prepare(tokenizer, "q" * 385, ["x"], 1024)
    with pytest.raises(worker.ProbeError, match="invalid_window"):
        worker.prepare(tokenizer, "q", ["x"], True)


def test_valid_output_exact_budget():
    assert probe.checked_events(encode(events())) == events()


@pytest.mark.parametrize("field,value", [
    ("scores", [True] * 20), ("scores", [float("nan")] * 20), ("scores", [1.1] * 20),
    ("tokens", [True] * 20), ("tokens", [513] * 20), ("durationMs", -1),
    ("durationMs", True), ("forwards", 11), ("peakAllocatedBytes", 0),
    ("extra", "private body"), ("caseId", "KRB-024"), ("window", 1024),
])
def test_invalid_output_is_never_persisted(field, value):
    items = events()
    items[2][field] = value
    with pytest.raises((worker.ProbeError, ValueError)):
        probe.checked_events(encode(items))


def test_failure_is_finite_and_never_claims_complete():
    failed = events()[:3] + [{"event": "failed", "reason": "cuda_oom", "forwards": 11, "warmupForwards": 2}]
    assert probe.checked_events(encode(failed))[-1]["reason"] == "cuda_oom"
    failed[-1]["reason"] = "raw exception private data"
    with pytest.raises(worker.ProbeError):
        probe.checked_events(encode(failed))
    with pytest.raises(worker.ProbeError):
        probe.checked_events(encode(events()[:-1]))
    with pytest.raises(worker.ProbeError):
        probe.checked_events(b'x' * (probe.LIMIT + 1))
    with pytest.raises(worker.ProbeError):
        probe.checked_events(b'{"event":"failed","event":"complete"}')


def test_model_hash_precedes_import_or_inference(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "file_hash", lambda p: calls.append(p.name) or "wrong")
    with pytest.raises(worker.ProbeError, match="cache_changed"):
        worker.execute(payload(), lambda e: pytest.fail("must not start model"))
    assert calls == ["model.safetensors"]


def test_current_input_binding_and_graded_metrics(source_replay_frozen_profile):
    rows, dataset, pool, profiles = probe.source.load_inputs()
    cases, saved, subset = probe.select_inputs(rows, dataset, pool)
    assert len(subset) == 70
    measured = probe.measure(events(), cases, saved, dataset, rows)
    assert len(measured) == 8
    for case in cases:
        arms = [m for m in measured if m["caseId"] == case.id]
        assert arms[0]["metrics"] == arms[1]["metrics"]
        assert [s["chunkId"] for s in arms[0]["ranked"]] == [s["chunkId"] for s in saved[case.id]["ranked"]]
        assert arms[0]["metrics"]["evidence_coverage"] == 1


def test_container_identity_rejects_drift(monkeypatch):
    calls = []
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout=b"wrong"))
    with pytest.raises(worker.ProbeError, match="container_changed"):
        probe.container_identity()
    assert len(calls) == 1


def test_worker_alive_is_unknown_on_observation_error(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=b""))
    with pytest.raises(worker.ProbeError, match="worker_alive"):
        probe.worker_alive("owned-synthetic-marker")


def test_main_failure_preserves_terminal_and_cannot_resume(tmp_path, monkeypatch, window_probe_frozen_inputs):
    result = tmp_path / "result.jsonl"
    monkeypatch.setattr(probe, "RESULT", result)
    monkeypatch.setattr(probe.source.base, "clean_head", lambda *a: "frozen-test-head")
    monkeypatch.setattr(probe, "container_identity", lambda: (_ for _ in ()).throw(worker.ProbeError("container_changed")))
    monkeypatch.setattr("sys.argv", ["probe", "--execute"])
    assert probe.main() == 1
    value = result.read_bytes()
    decoded = [json.loads(x) for x in value.splitlines()]
    assert [v["event"] for v in decoded] == ["prepared", "terminal"]
    assert decoded[-1]["sourceReads"] == 0 and decoded[-1]["workerStopped"] is True
    with pytest.raises(FileExistsError):
        probe.main()
    assert result.read_bytes() == value


@pytest.mark.parametrize("active,timeout,exit_code", [(False, False, 0), (True, False, 1), (False, True, 1)])
def test_main_complete_fake_and_cleanup_gate(tmp_path, monkeypatch, active, timeout, exit_code, window_probe_frozen_inputs):
    monkeypatch.setattr(probe, "RESULT", tmp_path / "result.jsonl")
    monkeypatch.setattr(probe.source.base, "clean_head", lambda *a: "frozen-test-head")
    monkeypatch.setattr(probe, "container_identity", lambda: None)
    monkeypatch.setattr(probe.source.base, "load_support", lambda: SimpleNamespace(checked_bytes=lambda *a: b'{}'))
    monkeypatch.setattr(probe.source, "SnapshotReader", lambda *a: SimpleNamespace(reads=0))
    monkeypatch.setattr(probe.source.base, "check_index", lambda *a: None)
    reader = SimpleNamespace(reads=0)
    def read_pool(pool):
        reader.reads += 1
        return {k: {} for k in pool}
    reader.read_pool = read_pool
    monkeypatch.setattr(probe.source, "SourceReader", lambda *a: reader)
    monkeypatch.setattr(probe, "payload_for", lambda *a: payload())
    worker_calls = []
    def run(*args):
        worker_calls.append(args)
        if timeout:
            raise worker.ProbeError("worker_timeout")
        return 0, encode(events())
    monkeypatch.setattr(probe, "run_worker", run)
    monkeypatch.setattr(probe, "worker_alive", lambda *a: active)
    monkeypatch.setattr("sys.argv", ["probe", "--execute"])
    assert probe.main() == exit_code
    assert len(worker_calls) == 1 and reader.reads == 7
    result = [json.loads(x) for x in probe.RESULT.read_bytes().splitlines()]
    assert result[-1]["status"] == ("failed" if active or timeout else "measured")
    assert result[-1]["workerStopped"] is not active
    assert len([v for v in result if v["event"] == "metrics"]) == (0 if timeout else 8)
    assert result[-1]["externalModelCalls"] == 0
    if timeout:
        assert result[-1]["counterStatus"] == "unknown" and result[-1]["forwards"] is None


@pytest.mark.parametrize("position,forwards,warmups", [(0, 1, 0), (1, 1, 2), (2, 0, 1), (3, 21, 2)])
def test_failure_counters_must_match_observed_phase(position, forwards, warmups):
    items = events()[:position] + [{"event": "failed", "reason": "inference_failed",
                                   "forwards": forwards, "warmupForwards": warmups}]
    with pytest.raises(worker.ProbeError, match="worker_output_invalid"):
        probe.checked_events(encode(items))


@pytest.mark.parametrize("mode", ["success", "overflow", "timeout", "broken_stdin"])
def test_worker_client_is_bounded_no_restart_and_no_raw_argv(monkeypatch, mode):
    calls, waits, kills = [], [], []
    class Input(io.BytesIO):
        def write(self, value):
            if mode == "broken_stdin":
                raise BrokenPipeError("must never escape")
            return super().write(value)
    process = SimpleNamespace(stdin=Input(), stdout=io.BytesIO(
        b'x' * (probe.LIMIT + 1) if mode == "overflow" else encode(events())), returncode=None)
    def wait(timeout):
        waits.append(timeout)
        if mode == "timeout" and timeout == 315:
            raise probe.subprocess.TimeoutExpired("owned docker client", timeout)
        process.returncode = 0
        return 0
    process.wait, process.poll = wait, lambda: process.returncode
    process.kill = lambda: kills.append(True)
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or process)
    if mode == "success":
        assert probe.run_worker(payload(), "owned-test-tag") == (0, encode(events()))
    else:
        with pytest.raises(worker.ProbeError, match="worker_timeout" if mode == "timeout" else "worker_output_invalid"):
            probe.run_worker(payload(), "owned-test-tag")
    assert len(calls) == 1
    command = calls[0][0][0]
    assert "300s" in command and "--kill-after=5s" in command
    assert payload()["cases"][0]["documents"][0] not in " ".join(command)
    assert calls[0][1]["stderr"] == probe.subprocess.DEVNULL
    assert waits == ([315, 5] if mode == "timeout" else [315])
    assert kills == ([True] if mode == "timeout" else [])


@pytest.mark.parametrize("fail_at", [None, 4])
def test_direct_forward_has_exact_budget_no_hidden_retry_or_download(tmp_path, monkeypatch, fail_at):
    calls, loads, emitted = [], [], []
    monkeypatch.setattr(worker, "CACHE", tmp_path)
    (tmp_path / "config.json").write_text('{"max_position_embeddings":8194}', encoding="utf-8")
    monkeypatch.setattr(worker, "file_hash", lambda p: worker.HASHES[p.name])
    # Changes to offline environment flags are restored by pytest.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "TOKENIZERS_PARALLELISM"):
        monkeypatch.setenv(name, "fake-original")
    class Batch(dict):
        def to(self, device):
            assert device == "cuda:0"
            return self
    class FakeTokenizer(Tokenizer):
        def pad(self, items, **kwargs):
            assert kwargs == {"padding": True, "return_tensors": "pt"}
            return Batch(size=len(items))
    class Logits:
        def __init__(self, size):
            self.size = size
        def view(self, value):
            assert value == -1
            return self
        def float(self):
            return self
        def cpu(self):
            return self
        def tolist(self):
            return [0.0] * self.size
    class Model:
        def half(self):
            return self
        def to(self, device):
            assert device == "cuda:0"
            return self
        def eval(self):
            return self
        def __call__(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == fail_at:
                raise RuntimeError("synthetic private exception")
            return SimpleNamespace(logits=Logits(kwargs["size"]))
    def load(kind, value):
        def inner(path, **kwargs):
            loads.append(kind)
            assert path == str(tmp_path)
            assert kwargs == {"local_files_only": True, "trust_remote_code": False}
            return value
        return SimpleNamespace(from_pretrained=inner)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=load("tokenizer", FakeTokenizer()), AutoModelForSequenceClassification=load("model", Model())))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="fake", inference_mode=contextlib.nullcontext,
        cuda=SimpleNamespace(is_available=lambda: True, synchronize=lambda: None, reset_peak_memory_stats=lambda: None,
                             max_memory_allocated=lambda: 1000, OutOfMemoryError=MemoryError)))
    assert worker.execute(payload(), emitted.append) == (0 if fail_at is None else 1)
    assert loads == ["tokenizer", "model"]
    assert len(calls) == (82 if fail_at is None else 4)
    assert emitted[-1]["forwards"] == (80 if fail_at is None else 2)
    assert emitted[-1]["warmupForwards"] == 2
    assert "synthetic private exception" not in json.dumps(emitted)
    assert len(probe.checked_events(encode(emitted))) == (11 if fail_at is None else 3)
