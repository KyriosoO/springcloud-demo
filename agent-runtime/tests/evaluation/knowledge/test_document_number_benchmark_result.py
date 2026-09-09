"""Recompute a real, immutable retrieval comparison without upgrading its scope."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e.knowledge_retrieval_benchmark_v1 import measure_case
from tests.system_e2e import knowledge_document_number_benchmark_v1 as runner


def test_same_corpus_comparison_preserves_non_reference_sources_and_recovers_loss():
    path = Path(__file__).with_name("retrieval_benchmark.document_number.result.v1.jsonl")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b50ee584b09dc3b8d724886240a25b0e9de23e046d5245ef5ef395b81e865299"
    rows = [json.loads(line) for line in raw.splitlines()]
    original = [json.loads(line) for line in runner.BASELINE.read_bytes().splitlines()]
    runner.validate_prepared(rows[0], runner.load_baseline())
    assert rows[0]["head"] == "cc1d305d5d2913cc55c02322c1b4244e0154f2be"
    source = subprocess.check_output(["git", "show", rows[0]["head"] +
        ":agent-runtime/tests/system_e2e/knowledge_document_number_benchmark_v1.py"], cwd=runner.base.REPO)
    assert hashlib.sha256(source).hexdigest() == rows[0]["comparisonSha256"]
    assert rows[0]["profileOverride"] == runner.FLAG
    cases = [row for row in rows if row["event"] == "case"]
    old_cases = {row["caseId"]: row for row in original if row["event"] == "case"}
    data = load_dataset()
    assert len(cases) == len(data.cases) == 24
    for case, row in zip(data.cases, cases, strict=True):
        assert row["caseId"] == case.id and row["status"] == "measured"
        assert row["metrics"] == measure_case(case, data, row["ranked"], row["evidence"])
        assert row["metrics"]["necessary_recall_at_k"] == row["metrics"]["evidence_coverage"] == 1
        assert row["metrics"]["mrr_at_k"] >= old_cases[case.id]["metrics"]["mrr_at_k"]
        assert row["metrics"]["precision_at_k"] is row["metrics"]["ndcg_at_k"] is None
        assert all(item["allowedOriginalClause"] for item in row["requiredSources"].values())
    improved = [row["caseId"] for row in cases if row["metrics"]["necessary_recall_at_k"] >
                old_cases[row["caseId"]]["metrics"]["necessary_recall_at_k"]]
    assert improved == ["KRB-006"]
    assert sum(row["metrics"]["mrr_at_k"] for row in cases) / 24 == pytest.approx(23.5 / 24)
    documents = ("KRB-003", "KRB-004", "KRB-005", "KRB-006", "KRB-008", "KRB-015", "KRB-023", "KRB-024")
    for row in cases:
        if row["caseId"] not in documents or row["split"] == "holdout":
            assert row["ranked"] == old_cases[row["caseId"]]["ranked"]
            assert row["metrics"] == old_cases[row["caseId"]]["metrics"]
    missing = next(row for row in cases if row["caseId"] == "KRB-006")
    assert [item["evidenceRank"] for item in missing["requiredSources"].values()] == [1, 2]
    assert all(item["pathRanks"][0]["path"] == "keyword" for item in missing["requiredSources"].values())
    terminal = rows[-1]
    assert terminal["event"] == "terminal" and terminal["status"] == "measured"
    assert terminal["casesMeasured"] == terminal["casesWithRequiredSources"] == 24
    assert terminal["counts"] == {"search": 54, "embedding": 24, "rerank": 29}
    assert terminal["profileFlagLaunches"] == terminal["startupRerankCalls"] == 1
    assert terminal["sourceAudits"] == terminal["clusterSettingReads"] == 2
    assert all(terminal[k] is True for k in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    assert all(terminal[k] == 0 for k in ("modelCalls", "businessCalls", "indexWrites", "retry", "resume"))
    paths = [row for row in rows if row["event"] == "retrieval_stage" and row["stage"] == "path"]
    assert len(paths) == 54 and all(0 <= row["durationMs"] <= 5000 for row in paths)
    assert terminal["limitations"] == ["manual_plans_not_rewrite", "no_summary", "not_functional_or_effectiveness_uat"]
