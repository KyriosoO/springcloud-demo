"""Finite real-source evidence validation; never opens ES or a model client."""
import hashlib
import json
import subprocess

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_evidence_source_replay_v1 as replay

RESULT_SHA = "01b9008cc662f24fe1abe50bea7d4d3779323d2f91a3b83314fe94b2a230281b"
RUN_HEAD = "6306c050388f5b1d2b6f99fddf8364674b1cd8f0"


def records():
    raw = replay.RESULT.read_bytes()
    assert len(raw) <= 256 * 1024 and hashlib.sha256(raw).hexdigest() == RESULT_SHA
    return [json.loads(line, object_pairs_hook=replay.base._unique, parse_constant=replay.base._reject_constant)
            for line in raw.splitlines()]


def test_source_replay_exact_schema_budgets_snapshot_and_source_provenance(source_replay_frozen_profile):
    rows = records()
    assert len(rows) == 26
    prepared, terminal = rows[0], rows[-1]
    assert set(prepared) == set("event head sourceResultSha256 datasetSha256 bindingSha256 catalogSha256 scriptSha256 selectorVersion selectorSha256 rerankInputVersion scoreModelProvenance sourcePoolCount sourceReadBudget snapshotReadBudget limitations".split())
    assert set(terminal) == set("event status casesMeasured requiredSourcesPreserved modelCalls embeddingCalls rerankCalls businessCalls indexWrites retry resume sourceReads snapshotReads rawContentPersisted limitations sourcePoolCount sourceMetadataFingerprint".split())
    assert prepared["event"] == "prepared" and terminal["event"] == "terminal"
    assert prepared["head"] == RUN_HEAD and prepared["sourceResultSha256"] == replay.SAVED_SHA
    saved, dataset, _, _ = replay.load_inputs()
    assert prepared["datasetSha256"] == dataset.sha256
    assert prepared["bindingSha256"] == replay.base.BINDING_SHA
    assert prepared["catalogSha256"] == replay.base.CATALOG_SHA
    assert prepared["scoreModelProvenance"] == saved[0]["localModelContainers"]
    assert prepared["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    assert prepared["selectorVersion"] == "optional-evidence-score-v1"
    for field, path in (("scriptSha256", "agent-runtime/tests/system_e2e/knowledge_evidence_source_replay_v1.py"),
                        ("selectorSha256", "agent-runtime/src/agent_runtime/knowledge/evidence/admission.py")):
        source = subprocess.check_output(["git", "show", f"{RUN_HEAD}:{path}"], cwd=replay.REPO)
        assert hashlib.sha256(source).hexdigest() == prepared[field]
    assert prepared["sourcePoolCount"] == terminal["sourcePoolCount"] == 504
    assert prepared["sourceReadBudget"] == terminal["sourceReads"] == 26
    assert prepared["snapshotReadBudget"] == terminal["snapshotReads"] == 6
    assert terminal["status"] == "measured" and terminal["rawContentPersisted"] is False
    assert terminal["casesMeasured"] == terminal["requiredSourcesPreserved"] == 24
    assert terminal["sourceMetadataFingerprint"] == "edc1ab713d748b25828c1b407a43bb4980bf2c85c2c477ee91a132a8aac1f74f"
    assert all(type(terminal[k]) is int and terminal[k] == 0 for k in (
        "modelCalls", "embeddingCalls", "rerankCalls", "businessCalls", "indexWrites", "retry", "resume"))
    assert prepared["limitations"] == terminal["limitations"] == replay.LIMITATIONS


def test_real_source_replay_retains_required_sources_without_claiming_precision():
    rows, dataset = records(), load_dataset()
    saved = [json.loads(line) for line in replay.SAVED.read_bytes().splitlines()]
    cases = {r["caseId"]: r for r in saved if r["event"] == "case"}
    totals = {group: [0, 0, 0, 0] for group in ("development", "holdout")}
    for case, row in zip(dataset.cases, rows[1:-1], strict=True):
        assert set(row) == {"event", "caseId", "split", "legacy", "candidate"}
        assert row["event"] == "case" and row["caseId"] == case.id and row["split"] == case.split
        assert row["legacy"]["evidence"] == cases[case.id]["evidence"]
        for key in ("legacy", "candidate"):
            value = row[key]
            assert set(value) == set("sufficient policyAllowed policyFingerprint payloadBytes evidence requiredSourcesPreserved metrics".split())
            assert value["sufficient"] is value["policyAllowed"] is value["requiredSourcesPreserved"] is True
            assert len(value["policyFingerprint"]) == 64
            assert type(value["payloadBytes"]) is int and 0 < value["payloadBytes"] <= 32768
            assert 1 <= len(value["evidence"]) <= 8
            assert all(set(e) == {"chunkId", "sha256"} for e in value["evidence"])
            metrics = replay.benchmark.measure_case(case, dataset, cases[case.id]["ranked"], value["evidence"])
            assert metrics == value["metrics"]
            assert metrics["necessary_recall_at_k"] == metrics["evidence_coverage"] == 1
            assert metrics["precision_at_k"] is metrics["ndcg_at_k"] is None
            assert metrics["judged_pool_size"] == 0
        assert row["candidate"]["payloadBytes"] <= row["legacy"]["payloadBytes"]
        group = totals[case.split]
        group[0] += len(row["legacy"]["evidence"])
        group[1] += len(row["candidate"]["evidence"])
        group[2] += row["legacy"]["payloadBytes"]
        group[3] += row["candidate"]["payloadBytes"]
    assert totals == {"development": [128, 97, 289425, 216252], "holdout": [64, 43, 142916, 91612]}


def test_read_only_result_contains_no_raw_payload_or_question_fields():
    banned = {"content", "question", "queryText", "focus", "prompt", "rawResponse", "authorization", "userToken", "quote"}
    def walk(value):
        if type(value) is dict:
            assert not banned.intersection(value)
            for item in value.values(): walk(item)
        elif type(value) is list:
            for item in value: walk(item)
    walk(records())
    assert b"Bearer " not in replay.RESULT.read_bytes()
