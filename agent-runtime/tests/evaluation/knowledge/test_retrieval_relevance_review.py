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
    assert (result["status"], result["reviewedCases"], result["totalCases"]) == ("partial", 12, 24)
    assert (result["reviewedPairs"], result["totalPairs"]) == (243, 483)
    assert result["overallGradedMetrics"] is None
    assert all(c["gradedMetrics"] is None and c["status"] == "unreviewed" for c in result["cases"][12:])
    assert all(c["status"] == "executor_reviewed" for c in result["cases"][:12])
    for case in result["cases"][:12]:
        for version, metrics in case["gradedMetrics"].items():
            assert metrics["unjudged_top_count"] == 0
            assert metrics["evidence_coverage"] == (0 if case["caseId"] == "KRB-006" and version == "baseline" else 1)


def test_initial_source_judgments_are_append_only():
    initial = b"\n".join(review.PATH.read_bytes().splitlines()[:6]) + b"\n"
    assert hashlib.sha256(initial).hexdigest() == "35d85862eba1f1b6994ac2b2c84cf06f29a0b74cd6e9115cdcea9550ee4ae200"


def test_second_source_review_batch_is_append_only():
    second = b"\n".join(review.PATH.read_bytes().splitlines()[:10]) + b"\n"
    assert hashlib.sha256(second).hexdigest() == "35e57fbe73ba5aca298c160786e343d5657a4f808169f63de18e94c8f1fed322"


def test_third_source_review_batch_is_append_only():
    third = b"\n".join(review.PATH.read_bytes().splitlines()[:15]) + b"\n"
    assert hashlib.sha256(third).hexdigest() == "d64b298fc18067be448feeecae51c1614e9a6e2226a102faaa809d871158d593"


def test_rank_scoring_matches_independent_arithmetic_and_shared_pool():
    result = review.evaluate_review()
    ledger = {v["caseId"]: v for v in rows() if v["event"] == "case_review"}
    for case in result["cases"][:12]:
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


def test_document_number_gain_does_not_hide_remaining_irrelevant_evidence():
    case = review.evaluate_review()["cases"][5]
    baseline, comparison = (case["gradedMetrics"][key] for key in ("baseline", "comparison"))
    assert baseline["necessary_recall_at_k"] == baseline["precision_at_k"] == 0
    assert comparison["necessary_recall_at_k"] == 1
    assert comparison["precision_at_k"] == 0.1
    assert comparison["ndcg_at_k"] == 1
    # Both selectors replay the improved retrieval pool. They are not a
    # comparison with the original retrieval baseline above.
    assert case["evidenceGradeCounts"] == {"legacy": [6, 0, 0, 2], "candidate": [6, 0, 0, 2]}


def test_background_grade_is_not_promoted_to_direct_support():
    case = review.evaluate_review()["cases"][4]
    assert case["evidenceGradeCounts"] == {"legacy": [0, 6, 1, 1], "candidate": [0, 6, 1, 1]}
    ledger = next(v for v in rows() if v.get("caseId") == "KRB-005")
    assert sum(v["grade"] == 3 for v in ledger["judgments"]) == 1
    assert all(v["grade"] == 1 for v in ledger["judgments"] if v["reason"] == "historical_parallel")


def test_same_instrument_and_similar_tax_terms_do_not_prove_direct_support():
    cases = review.evaluate_review()["cases"]
    assert cases[8]["evidenceGradeCounts"] == {"legacy": [3, 3, 1, 1], "candidate": [3, 3, 1, 1]}
    assert cases[10]["evidenceGradeCounts"] == {"legacy": [6, 1, 0, 1], "candidate": [2, 0, 0, 1]}
    # The required passage survives, but unrelated articles from the same
    # regulation survive too. Required-source coverage is not relevance.
    assert cases[10]["gradedMetrics"]["comparison"]["evidence_coverage"] == 1
    assert cases[10]["gradedMetrics"]["comparison"]["precision_at_k"] == 0.2
    judged = next(v for v in rows() if v.get("caseId") == "KRB-011")
    assert sum(v["reason"] == "other_requirement" for v in judged["judgments"]) == 16


def test_candidate_tail_reduction_is_not_a_new_retrieval_metric():
    cases = review.evaluate_review()["cases"]
    for index, legacy, candidate in ((9, [3, 4, 0, 1], [0, 2, 0, 1]),
                                      (11, [3, 4, 0, 1], [0, 3, 0, 1])):
        case = cases[index]
        assert case["evidenceGradeCounts"] == {"legacy": legacy, "candidate": candidate}
        assert case["gradedMetrics"]["baseline"] == case["gradedMetrics"]["comparison"]
        assert candidate[1] > 0  # Background remains; it is not an answer.


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
