"""Bind a scoped source inspection without treating observations as gold."""
import hashlib
import json
from pathlib import Path

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset


ROOT = Path(__file__).parent


def test_noise_inspection_is_source_bound_and_does_not_replace_qrels():
    raw_review = (ROOT / "retrieval_noise.source_inspection.v1.json").read_bytes()
    assert hashlib.sha256(raw_review).hexdigest() == "1b10c1db9e5e0a5ea44a56b3fee404f8e03ef0bf8fd0a810822d80be389a3f3e"
    review = json.loads(raw_review)
    assert set(review) == {"schemaVersion", "reviewId", "datasetSha256", "baselineSha256",
        "comparisonSha256", "reviewer", "status", "scope", "sourceCheck", "observations", "limitations"}
    assert review["schemaVersion"] == 1
    assert review["reviewId"] == "retrieval-noise-source-inspection-v1"
    assert review["reviewer"] == "codex_source_inspection_not_independent_human_approval"
    assert review["status"] == "diagnostic_not_qrels"
    assert review["scope"] == ["KRB-004_old_new_top20_union", "KRB-006_added_removed_only"]
    assert review["datasetSha256"] == load_dataset().sha256
    results = []
    for name, hash_key in (
        ("retrieval_benchmark.result.v1.jsonl", "baselineSha256"),
        ("retrieval_benchmark.document_number.result.v1.jsonl", "comparisonSha256"),
    ):
        raw = (ROOT / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == review[hash_key]
        results.append({r["caseId"]: r for line in raw.splitlines()
                        if (r := json.loads(line))["event"] == "case"})
    old, new = results
    expected = set()
    for case_id in ("KRB-004", "KRB-006"):
        before = {(s["chunkId"], s["sha256"]) for s in old[case_id]["ranked"]}
        after = {(s["chunkId"], s["sha256"]) for s in new[case_id]["ranked"]}
        pool = before | after if case_id == "KRB-004" else before ^ after
        expected.update((case_id, *source) for source in pool)
    rows = review["observations"]
    assert len(rows) == len(expected) == 25
    assert {(r["caseId"], r["chunkId"], r["sha256"]) for r in rows} == expected
    allowed = {"direct_definition", "older_document_same_definition", "same_document_other_subject",
               "direct_requested_period", "other_document_period", "other_subject"}
    for row in rows:
        assert set(row) == {"caseId", "chunkId", "sha256", "observation"}
        assert row["observation"] in allowed
    # These are traceable inspection notes, not automated relevance judgments.
    assert sum(r["observation"] == "direct_definition" for r in rows) == 1
    assert sum(r["observation"] == "direct_requested_period" for r in rows) == 2
    assert review["sourceCheck"] == {
        "indexName": "agent-doc-tax-policy-v5-20260907-vector-b2", "httpReads": 4,
        "returnedSources": 26, "uniqueSources": 25, "allContentHashesMatched": True,
        "rawContentPersisted": False, "modelCalls": 0, "indexWrites": 0,
    }
    assert review["limitations"] == ["not_complete_relevance_grades", "not_full_benchmark_precision",
        "not_new_uat", "no_source_equivalence_added", "not_current_law_advice", "holdout_not_used_for_tuning"]
    for record in new.values():
        assert record["metrics"]["precision_at_k"] is None
        assert record["metrics"]["ndcg_at_k"] is None


def test_development_only_score_probe_preserves_known_sources_but_is_not_selection():
    raw = (ROOT / "retrieval_benchmark.document_number.result.v1.jsonl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b50ee584b09dc3b8d724886240a25b0e9de23e046d5245ef5ef395b81e865299"
    rows = [json.loads(line) for line in raw.splitlines()]
    dataset = load_dataset()
    sources = {s.id: (s.chunk_id, s.sha256) for s in dataset.sources}
    observed = []
    for case in dataset.cases:
        if case.split != "development":
            continue
        record = next(r for r in rows if r["event"] == "case" and r["caseId"] == case.id)
        scores = {}
        for row in rows:
            if row.get("caseId") == case.id and row.get("stage") == "rerank":
                for item in row["candidates"]:
                    assert 0 <= item["score"] <= 1
                    key = (item["chunkId"], item["sha256"])
                    scores[key] = max(scores.get(key, 0.0), item["score"])
        # One exploratory cut, not a calibrated probability or production rule.
        # Any-focus maximum is NOT the V3 first-selection score or a selector replay.
        eligible = {(s["chunkId"], s["sha256"]) for s in record["ranked"]
                    if scores[(s["chunkId"], s["sha256"])] >= 0.5}
        assert {sources[s] for s in case.sources} <= eligible
        eligible_evidence = sum((s["chunkId"], s["sha256"]) in eligible for s in record["evidence"])
        observed.append((case.id, len(eligible), eligible_evidence))
    assert observed == [(f"KRB-{i:03d}", count, evidence) for i, (count, evidence) in enumerate(
        ((4, 4), (19, 8), (12, 8), (2, 2), (20, 8), (20, 8), (7, 7), (20, 8),
         (12, 8), (3, 3), (3, 3), (4, 4), (6, 6), (10, 8), (16, 8), (4, 4)), 1)]
