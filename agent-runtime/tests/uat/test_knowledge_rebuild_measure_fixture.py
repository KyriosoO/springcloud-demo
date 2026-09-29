"""Offline checks for the pre-registered UAT_02 question/source fixture."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard


PATH = Path(__file__).with_name("knowledge_rebuild_measure.v1.json")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_KEYS = {
    "id", "chunkId", "documentId", "domainId", "contentSha256", "locator", "officialUrl",
}
CASE_KEYS = {
    "caseId", "queryMode", "question", "expectedDomains", "necessarySources", "relatedSources",
    "retrievalDenominator", "expectedPublicStatus", "expectedReason", "obligations",
}


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _fixture() -> dict[str, object]:
    raw = PATH.read_bytes()
    assert 1 <= len(raw) <= 65536
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    assert type(value) is dict
    return value


def test_preregistered_questions_sources_and_thresholds_are_bounded() -> None:
    data = _fixture()
    assert set(data) == {
        "schemaVersion", "datasetId", "authority", "confirmation", "sourceReview", "sourceCorpus",
        "thresholds", "humanRubric", "sources", "cases", "limitations",
    }
    assert data["schemaVersion"] == 1
    assert data["datasetId"] == "knowledge-rebuild-measure-v1"
    assert "maintainer_confirmed" in data["confirmation"]
    binding = data["sourceCorpus"]
    assert binding["readAlias"] == "agent-doc-tax-policy-v2-read"
    assert binding["indexUuid"] == "jJ5Ww3LCRWWycfDkUZvmdw"
    assert binding["recordCount"] == 15521
    assert SHA256.fullmatch(binding["mappingSha256"])
    assert SHA256.fullmatch(binding["fullFingerprint"])
    assert binding["recheckRequiredBeforeExecution"] is True
    assert binding["contentHashBasis"] == "sha256(utf8(_source.content));not_legacy_contentHash"

    sources = data["sources"]
    assert type(sources) is list and len(sources) == 13
    source_ids: set[str] = set()
    chunks: set[str] = set()
    source_domains: dict[str, str] = {}
    for source in sources:
        assert type(source) is dict and set(source) == SOURCE_KEYS
        assert type(source["id"]) is str and re.fullmatch(r"[a-z0-9_]{1,40}", source["id"])
        assert type(source["chunkId"]) is str and 1 <= len(source["chunkId"]) <= 128
        assert source["id"] not in source_ids and source["chunkId"] not in chunks
        source_ids.add(source["id"])
        chunks.add(source["chunkId"])
        assert source["domainId"] in {"tax.policy", "tax.law"}
        assert type(source["contentSha256"]) is str and SHA256.fullmatch(source["contentSha256"])
        assert type(source["locator"]) is str and 1 <= len(source["locator"]) <= 100
        url = urlsplit(source["officialUrl"])
        assert url.scheme == "https" and url.hostname in {"www.chinatax.gov.cn", "fgk.chinatax.gov.cn"}
        source_domains[source["id"]] = source["domainId"]

    cases = data["cases"]
    assert type(cases) is list and len(cases) == 12
    assert [case["caseId"] for case in cases] == [f"UAT-KM-{i:03d}" for i in range(1, 13)]
    assert Counter(case["queryMode"] for case in cases) == {
        "lookup": 4, "explanation": 4, "applicability": 4,
    }
    assert sum(case["retrievalDenominator"] is True for case in cases) == 10
    assert all(case["retrievalDenominator"] is False for case in (cases[3], cases[9]))
    assert cases[6]["expectedDomains"] == ["tax.policy", "tax.law"]
    assert cases[3]["expectedDomains"] == ["tax.policy"]
    assert cases[3]["expectedReason"] == {
        "whenNoCandidate": "no_candidate", "whenCandidateLacksDirectEvidence": "insufficient_evidence",
    }
    assert cases[9]["expectedReason"] == "clarification_required"
    assert cases[11]["expectedReason"] == "insufficient_evidence"
    guard = QuestionEgressGuard()
    for case in cases:
        assert type(case) is dict and set(case) == CASE_KEYS
        assert type(case["question"]) is str and 1 <= len(case["question"]) <= 1024
        assert guard.evaluate(case["question"]).disposition is QuestionEgressDisposition.ALLOWED
        assert type(case["retrievalDenominator"]) is bool
        assert type(case["necessarySources"]) is list and len(set(case["necessarySources"])) == len(case["necessarySources"])
        assert type(case["relatedSources"]) is list and len(set(case["relatedSources"])) == len(case["relatedSources"])
        assert set(case["necessarySources"] + case["relatedSources"]) <= source_ids
        assert type(case["expectedDomains"]) is list and len(set(case["expectedDomains"])) == len(case["expectedDomains"])
        if case["retrievalDenominator"]:
            assert case["necessarySources"]
            assert set(case["expectedDomains"]) == {source_domains[s] for s in case["necessarySources"]}
        else:
            assert not case["necessarySources"]
            assert case["expectedDomains"] == (["tax.policy"] if case["caseId"] == "UAT-KM-004" else [])
        assert case["expectedPublicStatus"] in {"success", "no_result"}
        assert type(case["obligations"]) is list and case["obligations"]

    uat = data["thresholds"]["uat"]
    assert uat["cases"] == 12 and uat["minSourcedSearchCases"] == 8
    assert uat["queryModes"] == {"lookup": 4, "explanation": 4, "applicability": 4}
    assert uat["minMacroNecessarySourceRecallAt20"] == 0.8
    assert uat["minPrecisionAt20"] == 0.4
    assert uat["minAllFourHumanRubricPasses"] == 10
    assert uat["coreCases"] == ["UAT-KM-001", "UAT-KM-005", "UAT-KM-009"]
    assert uat["coreNecessarySourceZeroCoverageIsFailure"] is True
    assert uat["unsafeAffirmativeOrTemporalConfusionIsFailure"] is True
    comparison = data["thresholds"]["comparisonB"]
    assert comparison["mainMetric"] == "macro_necessary_source_recall_at20"
    assert comparison["mainMetricMustStrictlyImprove"] is True
    assert comparison["precisionAt20MayNotDecrease"] is True
    assert comparison["maxMedianRetrievalLatencyRatio"] == 1.1
    assert comparison["coreAndRetainedCaseCoverageMayNotDecrease"] is True
    assert comparison["retainedCases"] == [case["caseId"] for case in cases if case["retrievalDenominator"]]
    assert comparison["aComparisonState"] == "not_assessed"
    assert data["humanRubric"] == [
        "responds_to_original_question", "covers_all_expected_obligations", "no_unsupported_claim",
        "useful_for_lookup_or_clarification",
    ]


def test_gold_is_not_part_of_online_question_projection() -> None:
    data = _fixture()
    model_input = [{"caseId": c["caseId"], "question": c["question"]} for c in data["cases"]]
    encoded = json.dumps(model_input, ensure_ascii=False)
    for source in data["sources"]:
        assert source["id"] not in encoded
        assert source["chunkId"] not in encoded
        assert source["contentSha256"] not in encoded
        assert source["officialUrl"] not in encoded
