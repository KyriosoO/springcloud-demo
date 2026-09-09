"""Source judgments remain separate from online ranking and old run results."""
import copy
from dataclasses import replace
import hashlib
import json
import math

import pytest

from tests.evaluation.knowledge import retrieval_relevance_review as review


def rows():
    return [json.loads(line) for line in review.PATH.read_bytes().splitlines()]


def encode(values):
    return b"\n".join(json.dumps(v, ensure_ascii=False).encode() for v in values) + b"\n"


def test_partial_review_does_not_turn_unjudged_sources_into_zero():
    result = review.evaluate_review()
    assert (result["status"], result["reviewedCases"], result["totalCases"]) == ("partial", 4, 24)
    assert (result["reviewedPairs"], result["totalPairs"]) == (81, 483)
    assert result["overallGradedMetrics"] is None
    assert all(c["gradedMetrics"] is None and c["status"] == "unreviewed" for c in result["cases"][4:])
    assert all(c["status"] == "executor_reviewed" for c in result["cases"][:4])
    for case in result["cases"][:4]:
        for metrics in case["gradedMetrics"].values():
            assert metrics["unjudged_top_count"] == 0
            assert metrics["evidence_coverage"] == 1


def test_initial_source_judgments_are_append_only():
    initial = b"\n".join(review.PATH.read_bytes().splitlines()[:6]) + b"\n"
    assert hashlib.sha256(initial).hexdigest() == "35d85862eba1f1b6994ac2b2c84cf06f29a0b74cd6e9115cdcea9550ee4ae200"


def test_rank_scoring_matches_independent_arithmetic_and_shared_pool():
    result = review.evaluate_review()
    ledger = {v["caseId"]: v for v in rows() if v["event"] == "case_review"}
    for case in result["cases"][:4]:
        grades = {v["chunkId"]: v["grade"] for v in ledger[case["caseId"]]["judgments"]}
        ideal = sum((2 ** g - 1) / math.log2(i + 2)
                    for i, g in enumerate(sorted(grades.values(), reverse=True)[:20]))
        for name, key in (("baseline", "baselineSha256"), ("comparison", "comparisonSha256")):
            filename, _ = review.INPUTS[key]
            saved = [json.loads(line) for line in (review.DIRECTORY / filename).read_bytes().splitlines()]
            ranked = next(v for v in saved if v.get("event") == "case" and v["caseId"] == case["caseId"])["ranked"]
            expected_precision = sum(grades[v["chunkId"]] > 0 for v in ranked) / 20
            dcg = sum((2 ** grades[v["chunkId"]] - 1) / math.log2(i + 2) for i, v in enumerate(ranked))
            assert case["gradedMetrics"][name]["precision_at_k"] == expected_precision
            assert case["gradedMetrics"][name]["ndcg_at_k"] == pytest.approx(dcg / ideal)
    # Tail filtering did not improve retrieval ranking: this is a separate
    # Evidence policy comparison and does not get a fabricated new nDCG.
    assert "admission" not in result["cases"][0]["gradedMetrics"]


def test_evidence_grade_bins_keep_high_score_historical_parallel_visible():
    result = review.evaluate_review()
    case = result["cases"][3]
    assert case["evidenceGradeCounts"]["candidate"] == [0, 1, 0, 1]
    assert sum(case["evidenceGradeCounts"]["legacy"]) == 8
    assert "not_independent_blind_review" in result["limitations"]
    assert "no_equivalent_source_added" in result["limitations"]


@pytest.mark.parametrize("field,value", [
    ("schemaVersion", True), ("reviewer", "independent_human"),
    ("datasetSha256", "0" * 64), ("baselineSha256", "0" * 64),
    ("pool", "only_surviving_evidence"), ("rubric", {}), ("limitations", []),
])
def test_rejects_header_reinterpretation(field, value):
    values = rows()
    values[0][field] = value
    with pytest.raises(ValueError):
        review.evaluate_review(encode(values))


@pytest.mark.parametrize("field,value", [
    ("head", "x" * 40), ("auditId", "relevance-source-audit-raw-input"),
    ("bindingSha256", "0" * 64), ("sourcesRead", True), ("sourceReads", 55),
    ("snapshotReads", 0), ("allContentHashesMatched", 1),
    ("modelCalls", 1), ("retry", True), ("rawContentFilePersisted", True),
    ("freshReadAuthorization", True),
])
def test_rejects_unbounded_or_misrepresented_source_audit(field, value):
    values = rows()
    values[1][field] = value
    with pytest.raises(ValueError):
        review.evaluate_review(encode(values))


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "hash", "bad_type",
    "bool_grade", "reason_conflict", "unknown_reason", "unknown_basis", "unbacked_prior",
    "required_zero", "body", "unknown_case", "unknown_audit", "duplicate_case"])
def test_rejects_invalid_judgments_without_silently_scoring(mutation):
    values = rows()
    entry = values[2]
    item = entry["judgments"][0]
    if mutation == "missing":
        entry["judgments"].pop()
    elif mutation == "duplicate":
        entry["judgments"][1] = copy.deepcopy(item)
    elif mutation == "extra":
        entry["judgments"].append(copy.deepcopy(item))
    elif mutation == "hash":
        item["sha256"] = "0" * 64
    elif mutation == "bad_type":
        item["chunkId"] = []
    elif mutation == "bool_grade":
        item["grade"] = True
    elif mutation == "reason_conflict":
        item["grade"] = 3
    elif mutation == "unknown_reason":
        item["reason"] = "score_is_high"
    elif mutation == "unknown_basis":
        item["basis"] = "model_self_grade"
    elif mutation == "unbacked_prior":
        item["basis"] = "prior_inspection_current_hash_checked"
    elif mutation == "required_zero":
        direct = next(v for v in entry["judgments"] if v["grade"] == 3)
        direct.update(grade=0, reason="other_subject")
    elif mutation == "body":
        item["content"] = "must not be accepted or persisted"
    elif mutation == "unknown_case":
        entry["caseId"] = "KRB-999"
    elif mutation == "unknown_audit":
        entry["auditId"] = "not_checked"
    elif mutation == "duplicate_case":
        values.append(copy.deepcopy(entry))
    with pytest.raises(ValueError):
        review.evaluate_review(encode(values))


def test_empty_review_is_pending_not_perfect_precision():
    result = review.evaluate_review(encode(rows()[:2]))
    assert result["reviewedCases"] == 0
    assert result["reviewedPairs"] == 0
    assert all(c["gradedMetrics"] is None for c in result["cases"])


def test_dataset_and_ledger_cannot_drift_together(monkeypatch):
    original = review.load_dataset()
    monkeypatch.setattr(review, "load_dataset", lambda: replace(original, sha256="0" * 64))
    values = rows()
    values[0]["datasetSha256"] = "0" * 64
    with pytest.raises(ValueError):
        review.evaluate_review(encode(values))


def test_input_hashes_immutability_finite_shape_and_no_network(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **kw: pytest.fail("no network"))
    before = {name: hashlib.sha256((review.DIRECTORY / filename).read_bytes()).hexdigest()
              for name, (filename, _) in review.INPUTS.items()}
    result = review.evaluate_review()
    assert before == {name: sha for name, (_, sha) in review.INPUTS.items()}
    assert before == {name: hashlib.sha256((review.DIRECTORY / filename).read_bytes()).hexdigest()
                      for name, (filename, _) in review.INPUTS.items()}
    encoded = json.dumps(result)
    for forbidden in ("question", "queryText", "content", "quote", "Bearer", "systemInstruction"):
        assert forbidden not in encoded


@pytest.mark.parametrize("raw", [b"", b"x" * 262145, b"{}\n\n", b'{"x":1,"x":2}\n{}', b'NaN\n{}'],
                         ids=["empty", "oversized", "blank_line", "duplicate_key", "nonfinite"])
def test_rejects_invalid_encoding_or_size(raw):
    with pytest.raises(ValueError):
        review.evaluate_review(raw)
