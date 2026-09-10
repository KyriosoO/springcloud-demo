"""Recompute the finite ablation; never reinterpret it as an LLM or summary UAT."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e.knowledge_retrieval_benchmark_v1 import measure_case

RESULT = Path(__file__).with_name("query_representation.result.v1.jsonl")
SHA = "dc58b7f024740ea586b2e49e12e35f9f19631f99f719d307f26a30641f41e884"


def rows():
    raw=RESULT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    return [json.loads(line) for line in raw.splitlines()]


def test_readonly_arms_share_corpus_and_no_model_or_extra_path():
    records=rows()
    prepared,terminal=records[0],records[-1]
    assert prepared["event"] == "prepared"
    assert prepared["head"] == "8ae1cfe366d10353f789adb03349f9f9a9ff2ba8"
    source=subprocess.check_output(["git","show",prepared["head"]+
        ":agent-runtime/tests/system_e2e/knowledge_query_representation_probe.py"],cwd=Path(__file__).resolve().parents[4])
    assert hashlib.sha256(source).hexdigest() == prepared["probeSha256"]
    data=load_dataset()
    assert prepared["datasetSha256"] == data.sha256
    assert prepared["bindingSha256"] == data.binding_sha256
    assert prepared["selectorVersion"] == "optional-evidence-score-v1"
    assert prepared["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    assert prepared["arms"] == ["focused_both","original_keyword"]
    assert prepared["queryOrigin"] == "manual_focus_not_model_output"
    cases=[r for r in records if r.get("event") == "case"]
    assert [r["caseId"] for r in cases] == prepared["cases"] == [c.id for c in data.cases]
    assert terminal["status"] == "measured" and terminal["failureClass"] is None
    assert terminal["counts"] == prepared["limits"] == {"search":81,"embedding":27,"rerank":58}
    assert terminal["startupRerankCalls"] == 1
    assert all(terminal[k] == 0 for k in ("modelCalls","businessCalls","indexWrites","retry","resume"))
    assert [r for r in records if r.get("stage") == "cleanup"] == [dict(
        stage="cleanup",ownedProcessesStopped=True,rawLogsDeleted=True,secretScanPassed=True)]
    assert terminal["limitations"] == ["manual_focus_not_model_output",
        "not_production_stage_or_summary_uat","ungraded_precision_ndcg"]
    for c,r in zip(data.cases,cases,strict=True):
        assert len(r["paths"]) == 3*len(c.domains)
        assert r["counts"] == {"search":3*len(c.domains),"embedding":len(c.domains),"rerank":2*len(c.requirements)}
        for i,domain in enumerate(c.domains):
            paths=r["paths"][3*i:3*i+3]
            assert [p["path"] for p in paths] == ["original_keyword","focused_keyword","focused_vector"]
            assert all(p["domain"] == domain and p["count"] <= 20 for p in paths)
            focused=" ".join(req.focus for req in c.requirements if req.domain_id == domain)
            assert paths[0]["querySha256"] == hashlib.sha256(c.question.encode()).hexdigest()
            assert paths[1]["querySha256"] == paths[2]["querySha256"] == hashlib.sha256(focused.encode()).hexdigest()


@pytest.mark.parametrize("index", range(24))
def test_each_case_metrics_recompute_and_no_claim_about_unjudged_precision(index):
    data=load_dataset()
    case=data.cases[index]
    row=[r for r in rows() if r.get("event") == "case"][index]
    assert row["caseId"] == case.id and row["split"] == case.split
    for arm,value in row["arms"].items():
        assert value["metrics"] == measure_case(case,data,value["ranked"],value["evidence"])
        assert value["policyAllowed"] and value["selectionSufficient"]
        assert value["metrics"]["precision_at_k"] is value["metrics"]["ndcg_at_k"] is None
    a,b=[row["arms"][arm]["metrics"] for arm in ("focused_both","original_keyword")]
    assert b["necessary_recall_at_k"] == b["evidence_coverage"] == 1
    assert a["necessary_recall_at_k"] == a["evidence_coverage"] == (0.5 if case.id=="KRB-006" else 1)
    assert a["mrr_at_k"] == b["mrr_at_k"] == (0.5 if case.id=="KRB-013" else 1)


def test_missing_second_reference_is_a_path_loss_not_a_rerank_loss():
    row=next(r for r in rows() if r.get("event") == "case" and r["caseId"]=="KRB-006")
    original,focused,vector=row["paths"]
    assert original["requiredRanks"]["small_2023"] == [2]
    assert focused["requiredRanks"]["small_2023"] == vector["requiredRanks"]["small_2023"] == []
    assert row["arms"]["focused_both"]["poolRequiredRanks"]["small_2023"] == []
    assert row["arms"]["original_keyword"]["poolRequiredRanks"]["small_2023"]
