"""Explain frozen evidence noise without relabeling, threshold search or network IO."""
from collections import Counter

from tests.evaluation.knowledge import query_representation_relevance as review


def evidence_rows():
    validated = review.evaluate()
    assert validated["reviewSha256"] == "f8c60f201fb75173f14d6602214adda452c5b240619058e99bdd84b0b3556635"
    assert validated["status"] == "pool_reviewed" and validated["unjudgedPairs"] == 0
    old = {
        row["caseId"]: {review.prior.identity(item): item for item in row["judgments"]}
        for row in map(review.prior.decode, review.frozen_bytes(review.prior.PATH, review.PRIOR_SHA).splitlines())
        if row["event"] == "case_review"
    }
    additions = review.prior.decode(review.frozen_bytes(review.PATH, validated["reviewSha256"]))
    for row in additions["cases"]:
        for item in row["judgments"]:
            identity = review.prior.identity(item)
            assert identity not in old[row["caseId"]]
            old[row["caseId"]][identity] = item
    cases = {case.id: case for case in review.load_dataset().cases}
    records = map(review.prior.decode, review.frozen_bytes(review.ABLATION, review.ABLATION_SHA).splitlines())
    result = []
    for record in records:
        if record.get("event") != "case":
            continue
        case = cases[record["caseId"]]
        arm = record["arms"]["original_keyword"]
        ranks = {review.prior.identity(item): rank for rank, item in enumerate(arm["ranked"], 1)}
        assert len(ranks) == len(arm["ranked"])
        for position, item in enumerate(arm["evidence"], 1):
            identity = review.prior.identity(item)
            label = old[case.id][identity]
            result.append(dict(caseId=case.id, split=case.split, position=position,
                rank=ranks[identity], requirementCount=len(case.requirements),
                grade=label["grade"], reason=label["reason"]))
    return result


def test_frozen_noise_reasons_are_not_missing_corpus_or_unjudged_labels():
    rows = evidence_rows()
    assert len(rows) == 142
    assert Counter(row["grade"] for row in rows) == {0: 49, 1: 57, 2: 6, 3: 30}
    noise = [row for row in rows if row["grade"] == 0]
    assert len({row["caseId"] for row in noise}) == 17
    assert Counter(row["reason"] for row in noise) == {
        "other_requirement": 21, "other_subject": 19, "other_instrument": 9,
    }
    assert Counter(row["split"] for row in noise) == {"development": 31, "holdout": 18}
    assert sum(row["rank"] <= 3 for row in noise) == 13
    assert Counter(row["position"] for row in noise) == {2: 6, 3: 7, 4: 6, 5: 7, 6: 8, 7: 6, 8: 9}


def test_noise_is_beyond_maximum_anchor_prefix_not_forced_anchor_retention():
    noise = [row for row in evidence_rows() if row["grade"] == 0]
    # quality-v3 selects unique requirement anchors first, at most one per
    # requirement. Rank greater than that upper bound is necessarily optional;
    # the reverse inference (every earlier item is an anchor) is not valid.
    assert len(noise) == 49
    assert all(row["rank"] > row["requirementCount"] for row in noise)


def test_frozen_projection_cannot_support_exact_score_or_threshold_claims():
    records = list(map(review.prior.decode, review.frozen_bytes(review.ABLATION, review.ABLATION_SHA).splitlines()))
    assert records[0]["selectorVersion"] == "optional-evidence-score-v1"
    assert records[0]["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    for record in records:
        if record.get("event") == "case":
            for arm in record["arms"].values():
                for item in arm["ranked"] + arm["evidence"]:
                    assert set(item) == {"chunkId", "sha256"}
    # No exact score, margin, anchor ID or plaintext is reconstructed from rank.
