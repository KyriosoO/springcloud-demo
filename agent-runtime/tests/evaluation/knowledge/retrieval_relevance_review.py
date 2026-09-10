"""Offline source-review ledger and paired scoring for DR-KEV-033/034.

Judgments are supplied by source review, never inferred from scores, source
names, gold membership or a model answer. Unreviewed cases stay unscored.
This module does not approve production enablement or external human review.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from tests.evaluation.knowledge.retrieval_benchmark_dataset import (
    _constant, _obj, _unique, load_dataset,
)
from tests.evaluation.knowledge.retrieval_metrics import (
    RelevanceGrade, SourceRef, score_retrieval,
)

DIRECTORY = Path(__file__).parent
PATH = DIRECTORY / "retrieval_relevance.review.v1.jsonl"
ERROR = "knowledge.relevance_review_invalid"
DATASET_SHA = "ca076f8096ddf1210ddcf26da1a23135ee14c3cf415960fbaf03ea1e3a8f84f9"
INPUTS = {
    "baselineSha256": ("retrieval_benchmark.result.v1.jsonl", "1cc5f91c6ca5d7d9edb45354be17ca1c0b8a498b30c7e64cb3c78ff3febb521c"),
    "comparisonSha256": ("retrieval_benchmark.document_number.result.v1.jsonl", "b50ee584b09dc3b8d724886240a25b0e9de23e046d5245ef5ef395b81e865299"),
    "sourceReplaySha256": ("evidence_admission.source_replay.result.v1.jsonl", "01b9008cc662f24fe1abe50bea7d4d3779323d2f91a3b83314fe94b2a230281b"),
    "priorInspectionSha256": ("retrieval_noise.source_inspection.v1.json", "1b10c1db9e5e0a5ea44a56b3fee404f8e03ef0bf8fd0a810822d80be389a3f3e"),
}
REASONS = {
    "other_subject": 0, "other_requirement": 0, "other_instrument": 0,
    "scope_context": 1, "source_navigation": 1, "historical_parallel": 1,
    "procedural_context": 1, "partial_direct": 2, "direct_requirement": 3,
}
RUBRIC = {
    "0": "No requested fact or useful context; a shared topic or instrument alone is insufficient.",
    "1": "Useful navigation, scope or procedure context, or an explicitly different historical parallel; not a direct answer source.",
    "2": "Direct but incomplete support for one requested requirement.",
    "3": "Direct complete support for at least one explicit requirement, respecting the named instrument and period.",
}
LIMITATIONS = ["executor_assisted_not_external_human_approval", "not_current_legal_advice",
    "not_independent_blind_review", "no_equivalent_source_added",
    "no_online_tuning_or_production_enablement", "unreviewed_pairs_not_zero",
    "no_overall_graded_metrics_until_pool_complete"]


def require(condition: bool) -> None:
    if not condition:
        raise ValueError(ERROR)


def decode(raw: bytes) -> Any:
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_constant)


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(0 < len(raw) <= maximum)
    return raw


def identity(item: dict[str, Any]) -> SourceRef:
    return SourceRef(item["chunkId"], item["sha256"])


def grade_counts(evidence: list[dict[str, Any]], grades: dict[SourceRef, int]) -> list[int]:
    # The bins are descriptions, not an alternate pass threshold. Grade 1
    # cannot be promoted into direct support for the question.
    return [sum(grades[identity(item)] == grade for item in evidence) for grade in range(4)]


def evaluate_review(raw: bytes | None = None) -> dict[str, Any]:
    raw = bounded_bytes(PATH, 262144) if raw is None else raw
    require(type(raw) is bytes and 0 < len(raw) <= 262144)
    lines = raw.splitlines()
    require(2 <= len(lines) <= 49 and all(lines))
    ledger = [decode(line) for line in lines]
    header = _obj(ledger[0], "event schemaVersion reviewId reviewer datasetSha256 baselineSha256 comparisonSha256 sourceReplaySha256 priorInspectionSha256 pool rubric limitations")
    dataset = load_dataset()
    require(dataset.sha256 == DATASET_SHA)
    require(header == {"event": "review_header", "schemaVersion": 1,
        "reviewId": "retrieval-relevance-review-v1",
        "reviewer": "codex_source_review_not_external_human_approval",
        "datasetSha256": dataset.sha256,
        **{name: value[1] for name, value in INPUTS.items()},
        "pool": "baseline_comparison_top20_union_by_case", "rubric": RUBRIC,
        "limitations": LIMITATIONS} and type(header["schemaVersion"]) is int)
    assets: dict[str, Any] = {}
    for name, (filename, expected) in INPUTS.items():
        content = bounded_bytes(DIRECTORY / filename, 2097152)
        require(hashlib.sha256(content).hexdigest() == expected)
        assets[name] = ([decode(line) for line in content.splitlines()]
                        if filename.endswith("jsonl") else decode(content))
    prior = {(v["caseId"], identity(v)) for v in assets["priorInspectionSha256"]["observations"]}
    runs = [{v["caseId"]: v for v in assets[name] if v.get("event") == "case"}
            for name in ("baselineSha256", "comparisonSha256", "sourceReplaySha256")]
    pools = {c.id: {identity(v) for run in runs[:2] for v in run[c.id]["ranked"]} for c in dataset.cases}
    audits: set[str] = set()
    judgments: dict[str, tuple[RelevanceGrade, ...]] = {}
    for item in ledger[1:]:
        require(type(item) is dict)
        if item.get("event") == "source_audit":
            audit = _obj(item, "event auditId head bindingSha256 sourcesRead sourceReads snapshotReads allContentHashesMatched modelCalls indexWrites retry resume rawContentFilePersisted freshReadAuthorization")
            require(type(audit["auditId"]) is str
                    and re.fullmatch(r"relevance-source-audit-\d{8}-\d{2}", audit["auditId"]) is not None
                    and audit["auditId"] not in audits)
            require(type(audit["head"]) is str and len(audit["head"]) == 40
                    and all(c in "0123456789abcdef" for c in audit["head"])
                    and audit["bindingSha256"] == dataset.binding_sha256)
            for key, maximum in (("sourcesRead", 1080), ("sourceReads", 54), ("snapshotReads", 6)):
                require(type(audit[key]) is int and 0 < audit[key] <= maximum)
            require(audit["allContentHashesMatched"] is True
                    and audit["rawContentFilePersisted"] is False and audit["freshReadAuthorization"] is False)
            require(all(type(audit[k]) is int and audit[k] == 0 for k in ("modelCalls", "indexWrites", "retry", "resume")))
            audits.add(audit["auditId"])
            continue
        row = _obj(item, "event caseId auditId judgments")
        require(row["event"] == "case_review" and type(row["caseId"]) is str
                and row["caseId"] in pools and row["caseId"] not in judgments
                and type(row["auditId"]) is str and row["auditId"] in audits)
        require(type(row["judgments"]) is list and 1 <= len(row["judgments"]) <= 40)
        case_grades = []
        for value in row["judgments"]:
            v = _obj(value, "chunkId sha256 grade reason basis")
            require(type(v["grade"]) is int and type(v["reason"]) is str
                    and v["reason"] in REASONS and v["grade"] == REASONS[v["reason"]])
            require(v["basis"] in ("current_full_source_review", "prior_inspection_current_hash_checked"))
            require(type(v["chunkId"]) is str and type(v["sha256"]) is str)
            source = identity(v)
            require(source in pools[row["caseId"]])
            if v["basis"] == "prior_inspection_current_hash_checked":
                require((row["caseId"], source) in prior)
            case_grades.append(RelevanceGrade(source, v["grade"]))
        require(len(case_grades) == len(pools[row["caseId"]])
                and len({g.source for g in case_grades}) == len(case_grades)
                and {g.source for g in case_grades} == pools[row["caseId"]])
        judgments[row["caseId"]] = tuple(case_grades)
    require(bool(audits))
    sources = {s.id: SourceRef(s.chunk_id, s.sha256) for s in dataset.sources}
    results: list[dict[str, Any]] = []
    for case in dataset.cases:
        grades = judgments.get(case.id)
        if grades is None:
            results.append({"caseId": case.id, "status": "unreviewed", "gradedMetrics": None})
            continue
        graded = {g.source: g.grade for g in grades}
        scores = []
        for run in runs[:2]:
            row = run[case.id]
            scores.append(asdict(score_retrieval(corpus_state="present", k=20,
                ranked=tuple(identity(v) for v in row["ranked"]),
                evidence=tuple(identity(v) for v in row["evidence"]),
                required_groups=tuple((sources[s],) for s in case.sources), grades=grades)))
        replay = runs[2][case.id]
        results.append({"caseId": case.id, "status": "executor_reviewed",
            "gradedMetrics": {"baseline": scores[0], "comparison": scores[1]},
            "evidenceGradeCounts": {name: grade_counts(replay[name]["evidence"], graded)
                                     for name in ("legacy", "candidate")}})
    overall = None
    if len(judgments) == len(pools):
        # Equal weight per case, not per source. In particular the graded MRR
        # includes useful context; it is not the old required-source-only MRR.
        fields = ("necessary_recall_at_k", "mrr_at_k", "evidence_coverage",
                  "precision_at_k", "ndcg_at_k")
        overall = {version: {field: sum(row["gradedMetrics"][version][field]
                                        for row in results) / len(results)
                             for field in fields}
                   for version in ("baseline", "comparison")}
    return {"reviewId": header["reviewId"], "reviewSha256": hashlib.sha256(raw).hexdigest(),
        "status": "pool_reviewed" if len(judgments) == len(pools) else "partial",
        "reviewedCases": len(judgments), "totalCases": len(pools),
        "reviewedPairs": sum(len(v) for v in judgments.values()),
        "totalPairs": sum(len(v) for v in pools.values()),
        "overallGradedMetrics": overall, "limitations": LIMITATIONS, "cases": results}


if __name__ == "__main__":
    print(json.dumps(evaluate_review(), ensure_ascii=False, allow_nan=False))
