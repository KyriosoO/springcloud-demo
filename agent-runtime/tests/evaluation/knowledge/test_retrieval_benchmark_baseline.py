"""Read-only baseline accounting; measured retrieval is not a passed live UAT."""
import hashlib
import json
from pathlib import Path

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e.knowledge_retrieval_benchmark_v1 import measure_case


def test_baseline_preserves_real_loss_and_separate_scope():
    raw = Path(__file__).with_name("retrieval_benchmark.result.v1.jsonl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "1cc5f91c6ca5d7d9edb45354be17ca1c0b8a498b30c7e64cb3c78ff3febb521c"
    dataset = load_dataset()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert rows[0]["event"] == "prepared"
    assert rows[0]["head"] == "0727bfd8e8bceb62f5044dcd4bfd253ab7eff802"
    assert rows[0]["datasetSha256"] == dataset.sha256
    cases = [row for row in rows if row["event"] == "case"]
    assert len(cases) == 24
    for case, row in zip(dataset.cases, cases, strict=True):
        assert row["caseId"] == case.id and row["status"] == "measured"
        assert row["metrics"] == measure_case(case, dataset, row["ranked"], row["evidence"])
    losses = [row for row in cases if row["metrics"]["evidence_coverage"] < 1]
    assert [row["caseId"] for row in losses] == ["KRB-006"]
    assert losses[0]["selectionSufficient"] is True  # Structural check is not semantic proof.
    assert all(not value["pathRanks"] for value in losses[0]["requiredSources"].values())
    terminal = rows[-1]
    assert terminal["event"] == "terminal" and terminal["status"] == "measured"
    assert terminal["casesMeasured"] == 24 and terminal["casesWithRequiredSources"] == 23
    assert terminal["counts"] == {"search": 54, "embedding": 24, "rerank": 29}
    assert terminal["startupRerankCalls"] == 1 and terminal["sourceAudits"] == 2
    assert all(terminal[key] == 0 for key in ("modelCalls", "businessCalls", "indexWrites", "retry", "resume"))
    assert all(terminal[key] is True for key in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    assert terminal["limitations"] == ["manual_plans_not_rewrite", "no_summary", "not_functional_or_effectiveness_uat"]
