import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_offline_search_uses_exact_service_window_without_gold_in_query() -> None:
    path = Path(__file__).resolve().parents[1] / "scripts/compare-policy-vector-candidate.py"
    spec = importlib.util.spec_from_file_location("comparison_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vector = (0.25,) * 1024
    ann = module.search_body("test question", vector, "vector")
    assert ann["size"] == ann["knn"]["k"] == 21
    assert ann["knn"]["num_candidates"] == 100
    assert ann["knn"]["query_vector"] == vector
    assert set(ann["knn"]["filter"]) == {"terms"}
    assert "chunkId" not in str(ann["knn"])
    keyword = module.search_body("test question", vector, "keyword")
    assert keyword["query"]["bool"]["must"] == [{"multi_match": {
        "query": "test question", "fields": ["title", "content", "section"]}}]
    assert "knn" not in keyword
    with pytest.raises(ValueError):
        module.search_body("test", vector, "unsupported")


def test_optimized_interpreter_stops_before_argument_or_network_processing() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/compare-policy-vector-candidate.py"
    environment = {key: os.environ[key] for key in (
        "PATH", "SystemRoot", "USERPROFILE", "LOCALAPPDATA", "TEMP", "TMP",
    ) if key in os.environ}
    result = subprocess.run(
        [sys.executable, "-O", str(script), "--help"], check=False,
        capture_output=True, text=True, timeout=10, env=environment,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "failed", "reason": "comparison_failed_no_retry"}
    assert result.stderr == ""


def test_b2_finite_evidence_preserves_build_and_comparison_scope() -> None:
    directory = Path(__file__).resolve().parents[1] / "evidence/policy-vector-candidate-20260907-b2"
    hashes = {
        "binding.json": "26d9644b3c2b30511249b79c09399557ced6dfb6f11d526829e43c6e2296ee3f",
        "result.json": "71f08b8be07738ce2925b2931387ff9e5ec1c1b3840b7fbb6a0273a0664de518",
        "ann-comparison.json": "003929b26104b0d1b9724d0bd7666f4854fd44923a0df290ef35a46c10fb5eff",
    }
    records = {}
    for name, expected in hashes.items():
        raw = (directory / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        records[name] = json.loads(raw)
    build = records["result.json"]
    comparison = records["ann-comparison.json"]
    assert build["bindingSha256"] == comparison["bindingSha256"] == hashes["binding.json"]
    assert comparison["buildResultSha256"] == hashes["result.json"]
    assert build["status"] == "built_read_only_unpublished"
    assert build["result"]["total_count"] == 15521
    assert build["result"]["updated_count"] == 738
    assert build["paid"] == build["retry"] == build["resume"] == build["aliasWrites"] == 0
    assert comparison["paid"] == comparison["esWrites"] == comparison["aliasWrites"] == 0
    assert comparison["window"] == 20 and comparison["numCandidates"] == 100
    assert len(comparison["results"]) == 5
    for row in comparison["results"]:
        paths = row["candidate"]
        assert len(paths["keyword"]) == len(paths["vector"]) == len(row["required"])
        assert all(left is not None or right is not None
                   for left, right in zip(paths["keyword"], paths["vector"], strict=True))
    assert "not_full_uat" in comparison["limitations"]
    assert "not_typed_authorization_test" in comparison["limitations"]
