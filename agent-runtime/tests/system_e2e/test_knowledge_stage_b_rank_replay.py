"""Counterfactual diagnostics must not be mistaken for UAT or Evidence replay."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess

import httpx
import pytest

from tests.system_e2e import knowledge_stage_b_rank_replay as replay


def observed_case():
    return deepcopy(replay.run04.read("result.json")["cases"][2])


@pytest.mark.asyncio
async def test_report_reproduces_all_observed_orders_without_external_calls_or_writes(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline replay attempted external IO or file write")

    for owner, name in ((socket, "create_connection"), (socket, "getaddrinfo"),
                        (subprocess, "Popen"), (httpx.Client, "send"),
                        (httpx.AsyncClient, "send"), (Path, "write_text"), (Path, "write_bytes")):
        monkeypatch.setattr(owner, name, forbidden)
    result = await replay.report()
    assert result["scope"] == "rank-only-counterfactual-not-UAT-or-model-or-evidence-replay"
    assert result["externalCalls"] == 0
    rows = result["comparisons"]
    assert [(row["runId"], row["caseId"]) for row in rows] == [
        (replay.run01.read("result.json")["runId"], "UAT-KB-001"), (replay.run03.RUN_ID, "UAT-KB-015a"),
        (replay.run04.RUN_ID, "UAT-KB-015a"), (replay.run04.RUN_ID, "UAT-KB-004"),
    ]
    assert all(row["currentOrderReproduced"] for row in rows)
    for row in rows:
        assert set(row) == {"runId", "caseId", "currentOrderReproduced", "finalGoldRanks", "observedEvidenceGold"}
        assert set(row["finalGoldRanks"]) == {"current", *replay.MODES}
    last = rows[-1]
    assert last["finalGoldRanks"] == {
        "current": dict(lodging=9, living=None, law_rate=4),
        "keyword_first": dict(lodging=7, living=15, law_rate=4),
        "rerank_first": dict(lodging=9, living=None, law_rate=4),
        "rrf_keyword_rerank": dict(lodging=5, living=None, law_rate=4),
        "rrf_three_lists": dict(lodging=7, living=None, law_rate=4),
    }
    assert last["observedEvidenceGold"] == dict(lodging=False, living=False, law_rate=True)
    # Only observed Evidence booleans: no fabricated post-change Evidence result.
    serialized = json.dumps(result)
    for forbidden_key in ("question", "content", "chunkId", "sha256", "score", "JWT", "apiKey", "passed"):
        assert f'"{forbidden_key}"' not in serialized


@pytest.mark.asyncio
async def test_history_hash_mismatch_stops_before_parsing_or_replaying(monkeypatch):
    hashes = dict(replay.run01.HASHES, **{"manifest.json": "0" * 64})
    monkeypatch.setattr(replay.run01, "HASHES", hashes)
    with pytest.raises(ValueError, match="^replay.history_changed$"):
        await replay.report()


@pytest.mark.asyncio
async def test_current_production_rank_drift_is_not_silently_accepted(monkeypatch):
    async def changed_order(ranks):
        return ()

    monkeypatch.setattr(replay, "replay_current", changed_order)
    with pytest.raises(ValueError, match="^replay.current_order_mismatch$"):
        await replay.report()


def test_empty_keyword_path_is_valid_and_not_a_missing_path():
    case = json.loads((replay.run01.ROOT / "result.json").read_bytes())["cases"][0]
    ranks = replay.parse_ranks(case)
    law, = [domain for domain in ranks if domain.domain == "tax.law"]
    assert law.keyword == () and law.vector and law.rerank
    for mode in replay.MODES:
        assert law.rerank[0] in replay.experimental_order(ranks, mode)


@pytest.mark.parametrize("mutation,reason", [
    ("extra_path", "incomplete_stages"), ("extra_rerank", "incomplete_stages"),
    ("wrong_domain", "incomplete_path"), ("wrong_path", "incomplete_path"),
    ("duplicate_candidate", "invalid_candidate_identity"), ("invalid_hash", "invalid_candidate_identity"),
    ("too_many_path_candidates", "incomplete_path"), ("missing_rerank_candidate", "ambiguous_rerank_order"),
    ("extra_domain", "invalid_domains"), ("duplicate_domain", "invalid_domains"),
])
def test_incomplete_or_ambiguous_trace_fails_closed(mutation, reason):
    case = observed_case()
    paths = [row for row in case["retrievalStages"] if row["stage"] == "path"]
    reranks = [row for row in case["retrievalStages"] if row["stage"] == "rerank"]
    if mutation == "extra_path":
        case["retrievalStages"].append(deepcopy(paths[0]))
    elif mutation == "extra_rerank":
        case["retrievalStages"].append(deepcopy(reranks[0]))
    elif mutation == "wrong_domain":
        paths[0]["domain"] = "unknown"
    elif mutation == "wrong_path":
        paths[0]["path"] = "unknown"
    elif mutation == "duplicate_candidate":
        paths[0]["candidates"][1] = deepcopy(paths[0]["candidates"][0])
    elif mutation == "invalid_hash":
        paths[0]["candidates"][0]["sha256"] = "invalid"
    elif mutation == "too_many_path_candidates":
        paths[0]["candidates"].append(deepcopy(paths[0]["candidates"][0]))
    elif mutation == "missing_rerank_candidate":
        reranks[0]["candidates"].pop()
    elif mutation == "extra_domain":
        case["domains"].append("unknown")
    elif mutation == "duplicate_domain":
        case["domains"][1] = case["domains"][0]
    with pytest.raises(ValueError, match=f"^replay.{reason}$"):
        replay.parse_ranks(case)


@pytest.mark.parametrize("mode", replay.MODES)
def test_experiments_are_bounded_deterministic_unique_and_preserve_existing_anchors(mode):
    ranks = replay.parse_ranks(observed_case())
    order = replay.experimental_order(ranks, mode)
    assert order == replay.experimental_order(ranks, mode)
    assert len(order) == len(set(order)) == 20
    anchors = tuple(dict.fromkeys(key for domain in ranks for key in domain.keyword[:1] + domain.rerank[:1]))
    assert order[:len(anchors)] == anchors
    assert set(order) <= {key for domain in ranks for key in domain.rerank}


def test_experiments_do_not_take_gold_or_question_as_rank_input():
    case = observed_case()
    ranks = replay.parse_ranks(case)
    case["caseId"] = "not-a-UAT-case"
    case["question"] = "not-used"
    case["requiredGold"] = ["not-used"]
    assert replay.parse_ranks(case) == ranks
    with pytest.raises(ValueError, match="^replay.unknown_mode$"):
        replay.experimental_order(ranks, "gold-first")


def test_cross_domain_identity_and_content_conflicts_are_not_inferred():
    key = dict(chunkId="same-chunk", sha256="a" * 64)
    paths = [dict(stage="path", domain=domain, path=path, candidates=[dict(key)])
             for domain in ("tax.policy", "tax.law") for path in ("keyword", "vector")]
    reranks = [dict(stage="rerank", candidates=[dict(key)]) for _ in range(2)]
    case = dict(domains=["tax.policy", "tax.law"], retrievalStages=paths + reranks)
    with pytest.raises(ValueError, match="^replay.ambiguous_rerank_order$"):
        replay.parse_ranks(case)
    for row in paths[2:] + reranks[1:]:
        row["candidates"][0]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="^replay.content_conflict$"):
        replay.parse_ranks(case)
