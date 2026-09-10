"""Keep new relevance observations separate from frozen retrieval and paid UAT."""
import copy
import hashlib
import json
import math

import pytest

from tests.evaluation.knowledge import query_representation_relevance as review

LEDGER_SHA = "f8c60f201fb75173f14d6602214adda452c5b240619058e99bdd84b0b3556635"


def ledger():
    return json.loads(review.PATH.read_bytes())


def encoded(value):
    return json.dumps(value).encode()


def test_complete_frozen_review_reuses_only_exact_case_chunk_hash():
    assert hashlib.sha256(review.PATH.read_bytes()).hexdigest() == LEDGER_SHA
    result = review.evaluate()
    assert result["status"] == "pool_reviewed"
    assert [result[k] for k in ("poolPairs", "reusedPairs", "newPairs", "unjudgedPairs")] == [496, 459, 37, 0]
    assert len(result["cases"]) == 24
    assert all(c["status"] == "executor_reviewed" for c in result["cases"])
    assert all(c["gradedMetrics"][a]["unjudged_top_count"] == 0 for c in result["cases"] for a in review.ARMS)


def test_independent_rank_arithmetic_and_shared_union_ideal():
    rows = [json.loads(s) for s in review.ABLATION.read_bytes().splitlines()]
    ranked = {r["caseId"]: r for r in rows if r.get("event") == "case"}
    old = {r["caseId"]: {(j["chunkId"], j["sha256"]): j["grade"] for j in r["judgments"]}
           for r in map(json.loads, review.prior.PATH.read_bytes().splitlines()) if r["event"] == "case_review"}
    new = {r["caseId"]: {(j["chunkId"], j["sha256"]): j["grade"] for j in r["judgments"]}
           for r in ledger()["cases"]}
    for case in review.evaluate()["cases"]:
        arms = ranked[case["caseId"]]["arms"]
        pool = {(j["chunkId"], j["sha256"]) for a in arms.values() for j in a["ranked"]}
        labels = {s: g for s, g in (old[case["caseId"]] | new.get(case["caseId"], {})).items() if s in pool}
        assert set(labels) == pool
        ideal = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(sorted(labels.values(), reverse=True)[:20]))
        for arm, data in arms.items():
            ordered = [labels[j["chunkId"], j["sha256"]] for j in data["ranked"]]
            assert len(ordered) == 20
            metrics = case["gradedMetrics"][arm]
            assert metrics["precision_at_k"] == sum(g > 0 for g in ordered) / 20
            assert metrics["ndcg_at_k"] == pytest.approx(sum((2**g - 1) / math.log2(i + 2)
                                                          for i, g in enumerate(ordered)) / ideal)
            evidence = [labels[j["chunkId"], j["sha256"]] for j in data["evidence"]]
            assert case["evidenceGradeCounts"][arm] == [evidence.count(g) for g in range(4)]


def test_means_are_by_case_and_existing_holdout_is_not_new_blind_validation():
    result = review.evaluate()
    for split, n in (("development", 16), ("holdout", 8), ("all", 24)):
        summary = result["aggregates"][split]
        assert summary["reviewedCases"] == summary["totalCases"] == n
        rows = [r for r in result["cases"] if split == "all" or r["split"] == split]
        for arm in review.ARMS:
            for key, value in summary["gradedMetrics"][arm].items():
                assert value == pytest.approx(sum(r["gradedMetrics"][arm][key] for r in rows) / n)
    a, b = result["aggregates"]["all"]["gradedMetrics"].values()
    assert a["precision_at_k"] == pytest.approx(155 / 480)
    assert b["precision_at_k"] == pytest.approx(158 / 480)
    assert a["necessary_recall_at_k"] == pytest.approx(23.5 / 24)
    assert b["necessary_recall_at_k"] == 1
    assert "not_independent_blind_review" in result["limitations"]


def test_aggregate_improvement_does_not_hide_case_regression_or_evidence_noise():
    result = review.evaluate()
    case = result["cases"][14]
    assert case["caseId"] == "KRB-015"
    a, b = case["gradedMetrics"].values()
    assert b["ndcg_at_k"] < a["ndcg_at_k"]
    assert a["precision_at_k"] == b["precision_at_k"] == 0.65
    assert a["evidence_coverage"] == b["evidence_coverage"] == 1
    # Grade 1 is useful background, not direct support. Keep grade-zero noise.
    assert result["aggregates"]["all"]["evidenceGradeCounts"] == {
        "focused_both": [51, 58, 6, 29], "original_keyword": [49, 57, 6, 30]}


def test_partial_review_never_treats_missing_grades_as_zero_or_complete():
    value = ledger()
    value["cases"] = []
    result = review.evaluate(encoded(value))
    assert result["status"] == "partial" and result["unjudgedPairs"] == 37
    assert result["aggregates"]["all"]["gradedMetrics"] is None
    assert result["aggregates"]["all"]["reviewedCases"] == 19
    assert result["aggregates"]["holdout"]["reviewedCases"] == 8
    assert result["aggregates"]["holdout"]["gradedMetrics"] is not None
    assert result["cases"][0]["gradedMetrics"] is None


def test_missing_one_shared_pool_grade_blocks_both_arms_and_full_mean():
    value = ledger()
    value["cases"][-1]["judgments"].pop()
    value["cases"].pop()
    result = review.evaluate(encoded(value))
    assert result["unjudgedPairs"] == 1
    assert result["cases"][14]["gradedMetrics"] is None
    assert result["aggregates"]["all"]["gradedMetrics"] is None


@pytest.mark.parametrize("field,value", [
    ("schemaVersion", True), ("reviewer", "external_human"), ("datasetSha256", "0" * 64),
    ("bindingSha256", "0" * 64), ("ablationSha256", "0" * 64), ("priorReviewSha256", "0" * 64),
    ("pool", "evidence_only"), ("limitations", []), ("cases", {}),
])
def test_rejects_provenance_or_pool_reinterpretation(field, value):
    data = ledger()
    data[field] = value
    with pytest.raises(ValueError):
        review.evaluate(encoded(data))


@pytest.mark.parametrize("field,value", [
    ("head", "0" * 40), ("sourceReads", 2), ("snapshotReads", True), ("sourcesRead", 38),
    ("pairsRead", 36), ("allContentHashesMatched", 1), ("modelCalls", 1), ("indexWrites", 1),
    ("retry", True), ("resume", 1), ("rawContentFilePersisted", True), ("freshReadAuthorization", True),
])
def test_rejects_false_operational_audit(field, value):
    data = ledger()
    data["sourceAudit"][field] = value
    with pytest.raises(ValueError):
        review.evaluate(encoded(data))


@pytest.mark.parametrize("mutation", ["duplicate_case", "duplicate_source", "cross_case", "hash",
    "reason", "grade", "basis", "body", "old_grade", "unknown_case"])
def test_rejects_unsupported_judgments(mutation):
    data = ledger()
    row = data["cases"][0]
    item = row["judgments"][0]
    if mutation == "duplicate_case": data["cases"].append(copy.deepcopy(row))
    elif mutation == "duplicate_source": row["judgments"].append(copy.deepcopy(item))
    elif mutation == "cross_case": row["caseId"] = "KRB-006"
    elif mutation == "hash": item["sha256"] = "0" * 64
    elif mutation == "reason": item["reason"] = "high_score"
    elif mutation == "grade": item["grade"] = True
    elif mutation == "basis": item["basis"] = "model_self_grade"
    elif mutation == "body": item["content"] = "not allowed"
    elif mutation == "unknown_case": row["caseId"] = "KRB-999"
    elif mutation == "old_grade":
        prior_case = next(r for r in map(json.loads, review.prior.PATH.read_bytes().splitlines())
                          if r.get("caseId") == row["caseId"])
        row["judgments"][0] = copy.deepcopy(prior_case["judgments"][0])
    with pytest.raises(ValueError):
        review.evaluate(encoded(data))


@pytest.mark.parametrize("raw", [b"", b"x" * 32769, b'{"x":1,"x":2}', b"NaN"],
                         ids=["empty", "oversized", "duplicate_key", "nonfinite"])
def test_rejects_invalid_input_encoding(raw):
    with pytest.raises(ValueError): review.evaluate(raw)


@pytest.mark.parametrize("which", ["ablation", "prior"])
def test_changed_historical_file_is_not_reinterpreted(tmp_path, monkeypatch, which):
    invalid = tmp_path / "changed.json"
    invalid.write_bytes(b"{}")
    if which == "ablation": monkeypatch.setattr(review, "ABLATION", invalid)
    else: monkeypatch.setattr(review.prior, "PATH", invalid)
    with pytest.raises(ValueError): review.evaluate()


def test_no_network_writes_or_raw_content_and_original_null_metrics_unchanged(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("no network"))
    paths = [review.PATH, review.ABLATION, review.prior.PATH]
    before = [p.read_bytes() for p in paths]
    result = review.evaluate()
    assert [p.read_bytes() for p in paths] == before
    for row in map(json.loads, before[1].splitlines()):
        if row.get("event") == "case":
            assert all(a["metrics"]["precision_at_k"] is a["metrics"]["ndcg_at_k"] is None
                       for a in row["arms"].values())
    output = json.dumps(result)
    for forbidden in ("question", "content", "queryText", "quote", "Bearer", "systemInstruction"):
        assert forbidden not in output
