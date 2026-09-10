"""Frozen local measurement, not production approval or an end-to-end UAT."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from tests.system_e2e import knowledge_rerank_window_probe_v1 as probe

PATH = Path(__file__).with_name("rerank_window.result.v1.jsonl")
SHA = "2813ff8679cf9ef6c5623a42b35ec6755da5c407d3e968f7324fea94b8493bd4"
HEAD = "88c4fbea63523a0b793dd05253062e74f4d6cc0d"


def records():
    raw = PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    return [probe.worker.decode(line) for line in raw.splitlines()]


def test_frozen_source_and_input_identity():
    first = records()[0]
    assert first["event"] == "prepared" and first["head"] == HEAD
    for key, name in (("workerSha256", "knowledge_rerank_window_worker_v1.py"),
                      ("hostSha256", "knowledge_rerank_window_probe_v1.py")):
        result = subprocess.run(["git", "show", f"{HEAD}:agent-runtime/tests/system_e2e/{name}"],
                                cwd=probe.REPO, capture_output=True, timeout=10, check=True)
        assert hashlib.sha256(result.stdout).hexdigest() == first[key]
    # Later append-only relevance review must not invalidate this older prefix.
    prefix = b"".join(probe.review.PATH.read_bytes().splitlines(keepends=True)[:15])
    assert hashlib.sha256(prefix).hexdigest() == first["reviewSha256"] == probe.REVIEW_SHA
    rows, dataset, pool, profiles = probe.source.load_inputs()
    cases, saved, subset = probe.select_inputs(rows, dataset, pool)
    assert first["datasetSha256"] == dataset.sha256
    assert first["sourcePool"] == {k: list(v) for k, v in subset.items()}
    assert first["modelHashes"] == probe.worker.HASHES


def test_actual_counts_and_post_inference_metrics_recompute():
    data = records()
    events = probe.checked_events(b"\n".join(json.dumps(e).encode() for e in data
        if e["event"] in ("ready", "warmup", "arm", "complete", "failed")))
    assert len(events) == 11
    assert data[-1] == {"counterStatus": "confirmed", "event": "terminal", "externalModelCalls": 0,
        "forwards": 80, "indexWrites": 0, "reason": None, "scorePairs": 160, "snapshotReads": 6,
        "sourceReads": 7, "status": "measured", "warmupForwards": 2, "workerStopped": True}
    rows, dataset, pool, profiles = probe.source.load_inputs()
    cases, saved, subset = probe.select_inputs(rows, dataset, pool)
    assert probe.measure(events, cases, saved, dataset, rows) == [e for e in data if e["event"] == "metrics"]


def test_mixed_effects_do_not_satisfy_frozen_non_regression_criterion():
    metrics = {(r["caseId"], r["window"]): r for r in records() if r["event"] == "metrics"}
    changes = []
    for case in probe.worker.CASES:
        small, large = metrics[case, 512], metrics[case, 1024]
        assert small["metrics"]["evidence_coverage"] == large["metrics"]["evidence_coverage"] == 1
        assert small["metrics"]["precision_at_k"] == large["metrics"]["precision_at_k"]
        assert small["sameSavedTop1"] and small["maxSavedScoreDelta"] < 0.002
        changes.append(large["metrics"]["ndcg_at_k"] - small["metrics"]["ndcg_at_k"])
    assert sum(d > 0 for d in changes) == 2
    assert sum(d < 0 for d in changes) == 1
    assert sum(d == 0 for d in changes) == 1
    assert not all(d >= 0 for d in changes)


def test_finite_evidence_has_no_body_query_token_ids_or_credentials():
    forbidden = {"content", "query", "question", "documents", "input_ids", "jwt", "api_key",
                 "prompt", "rawResponse", "rawException", "authorization"}
    def visit(value):
        if isinstance(value, dict):
            assert not set(value) & forbidden
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
    visit(records())
