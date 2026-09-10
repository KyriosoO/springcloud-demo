"""DR-KEV-033: offline grading of the frozen query-representation comparison.

Reuse a judgment only for the same case, chunk and content hash. New judgments
come from bounded source review, never from rank, gold or model output. This
adds an observation without changing historical runs or online ranking.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from tests.evaluation.knowledge import retrieval_relevance_review as prior
from tests.evaluation.knowledge.retrieval_benchmark_dataset import _obj, load_dataset
from tests.evaluation.knowledge.retrieval_metrics import RelevanceGrade, SourceRef, score_retrieval

DIRECTORY = Path(__file__).parent
PATH = DIRECTORY / "query_representation.relevance.v1.json"
ABLATION = DIRECTORY / "query_representation.result.v1.jsonl"
ABLATION_SHA = "dc58b7f024740ea586b2e49e12e35f9f19631f99f719d307f26a30641f41e884"
PRIOR_SHA = "cba0ea89b26ca9334328d91f49d609c1cfad23fbfb6b63af72513ed6050d7e9e"
ARMS = ("focused_both", "original_keyword")
METRICS = ("necessary_recall_at_k", "mrr_at_k", "evidence_coverage", "precision_at_k", "ndcg_at_k")
LIMITATIONS = ["executor_assisted_not_external_human_approval", "not_independent_blind_review",
    "manual_focus_not_model_output", "no_summary_or_current_live_uat", "no_equivalent_source_added",
    "prior_judgments_reused_only_by_case_chunk_hash", "unreviewed_pairs_not_zero"]


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("knowledge.query_representation_review_invalid")


def frozen_bytes(path: Path, expected: str) -> bytes:
    raw = prior.bounded_bytes(path, 262144)
    require(hashlib.sha256(raw).hexdigest() == expected)
    return raw


def evaluate(raw: bytes | None = None) -> dict[str, Any]:
    raw = prior.bounded_bytes(PATH, 32768) if raw is None else raw
    require(type(raw) is bytes and 0 < len(raw) <= 32768)
    ledger = _obj(prior.decode(raw), "schemaVersion reviewId reviewer datasetSha256 bindingSha256 "
        "ablationSha256 priorReviewSha256 pool sourceAudit limitations cases")
    dataset = load_dataset()
    require(dataset.sha256 == prior.DATASET_SHA)
    expected = {"schemaVersion": 1, "reviewId": "query-representation-relevance-v1",
        "reviewer": "codex_source_review_not_external_human_approval", "datasetSha256": dataset.sha256,
        "bindingSha256": dataset.binding_sha256, "ablationSha256": ABLATION_SHA,
        "priorReviewSha256": PRIOR_SHA, "pool": "focused_both_original_keyword_top20_union_by_case",
        "limitations": LIMITATIONS}
    require(type(ledger["schemaVersion"]) is int and all(ledger[k] == v for k, v in expected.items()))
    audit = _obj(ledger["sourceAudit"], "head sourceReads snapshotReads sourcesRead pairsRead "
        "allContentHashesMatched modelCalls indexWrites retry resume rawContentFilePersisted freshReadAuthorization")
    require(audit["head"] == "e1ad6939e2b8d426afedfe5f08145f22445e2f63")
    for key, value in {"sourceReads": 1, "snapshotReads": 6, "sourcesRead": 37, "pairsRead": 37,
                       "modelCalls": 0, "indexWrites": 0, "retry": 0, "resume": 0}.items():
        require(type(audit[key]) is int and audit[key] == value)
    require(audit["allContentHashesMatched"] is True and audit["rawContentFilePersisted"] is False
            and audit["freshReadAuthorization"] is False)

    old_raw = frozen_bytes(prior.PATH, PRIOR_SHA)
    # Validate the original source-review contracts before reusing any labels.
    require(prior.evaluate_review(old_raw)["status"] == "pool_reviewed")
    old = {r["caseId"]: {prior.identity(v): v["grade"] for v in r["judgments"]}
           for r in map(prior.decode, old_raw.splitlines()) if r["event"] == "case_review"}
    records = list(map(prior.decode, frozen_bytes(ABLATION, ABLATION_SHA).splitlines()))
    require(records[0]["datasetSha256"] == dataset.sha256
            and records[0]["bindingSha256"] == dataset.binding_sha256
            and records[0]["arms"] == list(ARMS) and records[-1]["status"] == "measured")
    runs = {r["caseId"]: r for r in records if r.get("event") == "case"}
    require(list(runs) == [c.id for c in dataset.cases])
    pools = {c.id: {prior.identity(v) for arm in ARMS for v in runs[c.id]["arms"][arm]["ranked"]}
             for c in dataset.cases}
    additions: dict[str, dict[SourceRef, int]] = {}
    require(type(ledger["cases"]) is list and len(ledger["cases"]) <= 5)
    for row in ledger["cases"]:
        row = _obj(row, "caseId judgments")
        cid = row["caseId"]
        require(type(cid) is str and cid in pools and cid not in additions)
        require(type(row["judgments"]) is list and 1 <= len(row["judgments"]) <= 40)
        case_grades = {}
        for item in row["judgments"]:
            item = _obj(item, "chunkId sha256 grade reason basis")
            require(type(item["chunkId"]) is str and type(item["sha256"]) is str)
            source = prior.identity(item)
            require(source in pools[cid] and source not in old[cid] and source not in case_grades)
            require(type(item["grade"]) is int and type(item["reason"]) is str
                    and item["reason"] in prior.REASONS and item["grade"] == prior.REASONS[item["reason"]]
                    and item["basis"] == "current_full_source_review")
            case_grades[source] = item["grade"]
        additions[cid] = case_grades

    sources = {s.id: SourceRef(s.chunk_id, s.sha256) for s in dataset.sources}
    results = []
    for case in dataset.cases:
        pool = pools[case.id]
        reused = {s: g for s, g in old[case.id].items() if s in pool}
        grades = reused | additions.get(case.id, {})
        missing = pool - grades.keys()
        row: dict[str, Any] = {"caseId": case.id, "split": case.split, "poolPairs": len(pool),
            "reusedPairs": len(reused), "newPairs": len(grades) - len(reused),
            "unjudgedPairs": len(missing), "status": "unreviewed" if missing else "executor_reviewed",
            "gradedMetrics": None, "evidenceGradeCounts": None}
        # Do not score only the covered arm or use an incomplete shared ideal
        # pool. Unjudged candidates stay missing, not grade zero.
        if not missing:
            judgments = tuple(RelevanceGrade(s, g) for s, g in grades.items())
            row["gradedMetrics"] = {}
            row["evidenceGradeCounts"] = {}
            for arm in ARMS:
                value = runs[case.id]["arms"][arm]
                row["gradedMetrics"][arm] = asdict(score_retrieval(corpus_state="present", k=20,
                    ranked=tuple(prior.identity(v) for v in value["ranked"]),
                    evidence=tuple(prior.identity(v) for v in value["evidence"]),
                    required_groups=tuple((sources[s],) for s in case.sources), grades=judgments))
                row["evidenceGradeCounts"][arm] = prior.grade_counts(value["evidence"], grades)
        results.append(row)

    aggregates = {}
    for split in ("development", "holdout", "all"):
        selected = [r for r in results if split == "all" or r["split"] == split]
        complete = all(r["unjudgedPairs"] == 0 for r in selected)
        aggregates[split] = {"totalCases": len(selected), "reviewedCases": sum(r["unjudgedPairs"] == 0 for r in selected),
            "gradedMetrics": {arm: {m: sum(r["gradedMetrics"][arm][m] for r in selected) / len(selected)
                                    for m in METRICS} for arm in ARMS} if complete else None,
            "evidenceGradeCounts": {arm: [sum(r["evidenceGradeCounts"][arm][g] for r in selected)
                                           for g in range(4)] for arm in ARMS} if complete else None}
    return {"reviewId": expected["reviewId"], "reviewSha256": hashlib.sha256(raw).hexdigest(),
        "status": "pool_reviewed" if all(r["unjudgedPairs"] == 0 for r in results) else "partial",
        **{key: sum(r[key] for r in results) for key in ("poolPairs", "reusedPairs", "newPairs", "unjudgedPairs")},
        "aggregates": aggregates, "cases": results, "limitations": LIMITATIONS}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, allow_nan=False))
