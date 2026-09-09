"""Read-only layered rescoring; never change a frozen run's UAT verdict."""
import hashlib
import json
from pathlib import Path

import pytest

from tests.evaluation.knowledge.retrieval_metrics import SourceRef, score_retrieval
from tests.system_e2e.knowledge_stage_b_cases import CASES, GOLD

ROOT = Path(__file__).resolve().parents[2] / "system_e2e"
RUNS = (
    ("11", "2025550720405361a79d659cf02dc500dfb5561c983171d6b7bd5cf01e0d0392", 200, 1, (1, 4)),
    ("12", "8122f04207e4cead37727b49818aeb62618b0139cc6085043bf919a9a2f43ac1", 502, 0, (1, 7)),
)


@pytest.mark.parametrize("run,sha,http,points,positions", RUNS)
def test_recalled_required_sources_are_not_zeroed_by_answer_failure(run, sha, http, points, positions):
    path = ROOT / f"knowledge_stage_b_run_{run}" / "result.json"
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == sha
    result = json.loads(original)
    row = next(item for item in result["cases"] if item["caseId"] == "UAT-KB-015a")
    final_rank = [stage for stage in row["retrievalStages"] if stage["stage"] == "final_rank"]
    evidence = [stage for stage in row["retrievalStages"] if stage["stage"] == "evidence"]
    assert len(final_rank) == len(evidence) == 1
    ranked_refs = tuple(SourceRef(item["chunkId"], item["sha256"]) for item in final_rank[0]["candidates"])
    evidence_refs = tuple(SourceRef(item["chunkId"], item["sha256"]) for item in evidence[0]["candidates"])
    groups = tuple((SourceRef(GOLD[name]["chunk"], GOLD[name]["sha256"]),) for name in ("lodging", "living"))
    metrics = score_retrieval(corpus_state="present", k=20, ranked=ranked_refs, evidence=evidence_refs, required_groups=groups)
    assert tuple(evidence_refs.index(group[0]) + 1 for group in groups) == positions
    assert metrics.necessary_recall_at_k == metrics.evidence_coverage == metrics.mrr_at_k == 1.0
    # No graded labels were recorded: precision/nDCG cannot be invented now.
    assert metrics.precision_at_k is metrics.ndcg_at_k is None
    assert metrics.unjudged_top_count == 20 and metrics.judged_pool_size == 0
    assert all(group[0].sha256 in row["evidenceContentHashes"] for group in groups)
    assert all(item["status"] == "succeeded" for item in row["modelTasks"])
    assert row["httpStatus"] == http and row["pointCount"] == points
    assert row["passed"] is False and result["status"] == "failed"
    assert path.read_bytes() == original


def test_manual_plan_eight_case_retrieval_is_not_end_to_end_accuracy():
    path = ROOT.parents[2] / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-context-paired-20260908-01.jsonl"
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == "beae7ddda48b4afd8382c975f1cb107c0e24a6d489b497808c6a82a4d8b35275"
    records = [json.loads(line) for line in original.splitlines()]
    rows = [row for row in records if "requiredSources" in row]
    expected = {case["caseId"]: case["requiredGold"] for case in CASES if case["requiredGold"]}
    assert len(rows) == 8 and {row["caseId"] for row in rows} == set(expected)
    for row in rows:
        groups = tuple((SourceRef(GOLD[name]["chunk"], GOLD[name]["sha256"]),) for name in expected[row["caseId"]])
        ranked = tuple(SourceRef(item["chunkId"], item["sha256"]) for item in row["ranked"])
        evidence = tuple(SourceRef(item["chunkId"], item["sha256"]) for item in row["evidence"])
        value = score_retrieval(corpus_state="present", k=20, ranked=ranked, evidence=evidence, required_groups=groups)
        assert value.necessary_recall_at_k == value.evidence_coverage == 1.0
        assert value.precision_at_k is value.ndcg_at_k is None
    terminal = records[-1]
    assert terminal["modelCalls"] == terminal["indexWrites"] == 0
    assert terminal["limitations"] == ["manual_plans_not_rewrite", "no_summary", "not_functional_or_effectiveness_uat"]
    assert path.read_bytes() == original
