from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DIAGNOSIS = Path(__file__).with_name("diagnostics") / "candidate_05_effect_diagnosis.v1.json"
DATASET = Path(__file__).with_name("representative_questions.v2.jsonl")


def test_candidate_05_diagnosis_is_read_only_reproducible_and_actionable() -> None:
    diagnosis = json.loads(DIAGNOSIS.read_bytes())
    source = diagnosis["source"]
    result_path = REPOSITORY_ROOT / source["resultPath"]
    manifest_path = REPOSITORY_ROOT / source["manifestPath"]
    authorization_path = REPOSITORY_ROOT / source["authorizationPath"]
    assert _sha256(result_path) == source["resultSha256"]
    assert _sha256(manifest_path) == source["manifestSha256"]
    assert _sha256(authorization_path) == source["authorizationSha256"]

    result = json.loads(result_path.read_bytes())
    dataset = {
        item["case_id"]: item
        for item in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines())
    }
    assert result["runId"] == source["runId"]
    assert result["conclusion"] == diagnosis["historicalConclusion"] == "partially_effective"
    for key, value in diagnosis["metrics"].items():
        assert result["aggregateMetrics"][key] == value

    rows = result["caseResults"]
    primary = [row["primary"] for row in rows]
    answerable = [row for row in rows if dataset[row["caseId"]]["expected_answerability"] == "answerable"]
    security_negative = [row for row in rows if dataset[row["caseId"]]["category"] == "security_negative"]
    distributions = diagnosis["distributions"]
    assert len(rows) == distributions["caseCount"]
    assert len(answerable) == distributions["answerableCount"]
    assert len(security_negative) == distributions["securityNegativeCount"]
    assert Counter(item["terminalStatus"] for item in primary) == distributions["terminalStatus"]
    assert Counter(item["summaryStatus"] for item in primary) == distributions["summaryStatus"]
    assert Counter(row["primaryJudgment"]["judgmentReason"] for row in rows) == distributions["judgmentReason"]

    historical_summary = [item["summaryStatus"] in {"answer", "insufficient_evidence"} for item in primary]
    safety_eligible_summary = [
        row["primary"]["summaryStatus"] in {"answer", "insufficient_evidence"}
        for row in rows
        if dataset[row["caseId"]]["category"] != "security_negative"
    ]
    answerable_quality = [
        row for row in answerable if row["primaryJudgment"]["judgmentReason"] != "gold_issue"
    ]
    denominator = diagnosis["denominatorAnalysis"]
    assert _ratio(historical_summary, numerator_key="valid") == denominator["historicalSummary"]
    assert _ratio(safety_eligible_summary, numerator_key="valid") == denominator["safetyCompatibleSummary"]
    assert _ratio([row["primaryJudgment"]["faithful"] for row in answerable]) == denominator["historicalFaithfulness"]
    assert _ratio([row["primaryJudgment"]["faithful"] for row in answerable_quality]) == denominator["qualityEligibleFaithfulness"]
    assert _ratio([row["primaryJudgment"]["useful"] for row in answerable]) == denominator["historicalUsefulness"]
    assert _ratio([row["primaryJudgment"]["useful"] for row in answerable_quality]) == denominator["qualityEligibleUsefulness"]
    gold_issue_case_ids = sorted(
        row["caseId"] for row in answerable if row["primaryJudgment"]["judgmentReason"] == "gold_issue"
    )
    assert gold_issue_case_ids == denominator["answerableGoldIssueCaseIds"]
    assert len(gold_issue_case_ids) == denominator["answerableGoldIssueCount"]

    coverage_by_id = {item["caseId"]: item for item in diagnosis["coverageCases"]}
    assert set(coverage_by_id) == {
        "draft-mixed-eit-article-28-policy",
        "draft-mixed-collection-article-32-policy",
        "draft-mixed-vat-law-2026-policy",
    }
    for row in rows:
        if row["caseId"] not in coverage_by_id:
            continue
        expected = coverage_by_id[row["caseId"]]
        case = dataset[row["caseId"]]
        variant = row["primary"]
        assert row["primaryJudgment"]["judgmentReason"] == "coverage"
        assert variant["metrics"]["fusionRecallAt10"] == expected["fusionRecallAt10"]
        assert variant["metrics"]["rerankRecallAt10"] == expected["rerankRecallAt10"]
        assert variant["metrics"]["requiredEvidenceCoverage"] == expected["requiredEvidenceCoverage"]
        assert len(variant["adoptedEvidenceIds"]) == expected["adoptedEvidenceCount"]
        assert len(case["required_evidence_ids"]) == expected["requiredEvidenceCount"]

    assert {item["id"] for item in diagnosis["rootCauses"]} == {
        "security_negative_summary_denominator_conflict",
        "answerable_gold_issue_attribution_conflict",
        "mixed_domain_summary_coverage_gap",
        "mixed_domain_retrieval_gap",
    }
    decision = diagnosis["optimizationDecision"]
    assert decision["summaryTaskVersion"] == "4"
    assert decision["changeRetrievalWeightsInitially"] is False
    assert decision["changeDatasetOrGold"] is False
    assert decision["changeValidator"] is False
    assert decision["changeAuthorizationOrEgressPolicy"] is False


def test_candidate_05_diagnosis_contains_no_questions_or_model_payloads() -> None:
    diagnosis = json.loads(DIAGNOSIS.read_bytes())
    serialized = json.dumps(diagnosis, ensure_ascii=False).lower()
    for forbidden_key in (
        '"question"',
        '"quote"',
        '"content"',
        '"modelresponse"',
        '"jwt"',
        '"prompt"',
    ):
        assert forbidden_key not in serialized


def _ratio(values: list[bool], *, numerator_key: str = "passed") -> dict[str, float | int]:
    passed = sum(values)
    eligible = len(values)
    return {numerator_key: passed, "eligible": eligible, "rate": passed / eligible}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
