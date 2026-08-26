from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DIAGNOSIS = Path(__file__).with_name("diagnostics") / "candidate_04_effect_diagnosis.v1.json"
DATASET = Path(__file__).with_name("representative_questions.v2.jsonl")


def test_candidate_04_diagnosis_is_read_only_reproducible_and_actionable() -> None:
    diagnosis = json.loads(DIAGNOSIS.read_bytes())
    source = diagnosis["source"]
    result_path = REPOSITORY_ROOT / source["resultPath"]
    manifest_path = REPOSITORY_ROOT / source["manifestPath"]
    authorization_path = REPOSITORY_ROOT / source["authorizationPath"]
    assert _sha256(result_path) == source["resultSha256"]
    assert _sha256(manifest_path) == source["manifestSha256"]
    assert _sha256(authorization_path) == source["authorizationSha256"]

    result = json.loads(result_path.read_bytes())
    assert result["runId"] == source["runId"]
    assert result["conclusion"] == diagnosis["historicalConclusion"] == "ineffective"
    aggregate = result["aggregateMetrics"]
    metrics = diagnosis["metrics"]
    for key in (
        "domainExactMatchRate",
        "fusionRecallAt10",
        "fusionMrrAt10",
        "rerankRecallAt10",
        "rerankMrrAt10",
        "requiredEvidenceCoverage",
        "summaryValidCompletionRate",
        "citationValidityRate",
        "faithfulnessRate",
        "usefulnessRate",
        "q1",
        "q2",
        "q3",
        "q4",
    ):
        assert aggregate[key] == metrics[key]
    assert set(aggregate["pathHitAt10ByDomainPath"].values()) == {metrics["pathHitAt10"]}

    primary = [case["primary"] for case in result["caseResults"]]
    assert Counter(item["terminalStatus"] for item in primary) == diagnosis["distributions"]["terminalStatus"]
    assert Counter(item["summaryStatus"] for item in primary) == diagnosis["distributions"]["summaryStatus"]
    assert Counter(case["primaryJudgment"]["judgmentReason"] for case in result["caseResults"]) == diagnosis["distributions"]["judgmentReason"]

    expected_domains = {
        item["case_id"]: item["expected_domain_ids"]
        for item in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines())
    }
    mismatches = sorted(
        case["caseId"]
        for case in result["caseResults"]
        if case["primary"]["selectedDomainIds"] != expected_domains[case["caseId"]]
        and case["primary"]["terminalStatus"] not in {"model_egress_denied"}
    )
    assert mismatches == diagnosis["domainMismatchCaseIds"]

    assert {item["id"] for item in diagnosis["rootCauses"]} == {
        "domain_selector_generic_overselection",
        "domain_selector_tax_law_lexical_gap",
        "summary_single_point_undercoverage",
        "dataset_gold_or_corpus_issue",
    }
    assert diagnosis["optimizationDecision"] == {
        "domainCatalogVersion": "tax-domain-catalog-v2",
        "summaryTaskVersion": "3",
        "changeRetrievalWeights": False,
        "changeDatasetOrGold": False,
        "changeValidator": False,
        "reason": "domain and summary changes are directly supported; retrieval and validator changes are not",
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
