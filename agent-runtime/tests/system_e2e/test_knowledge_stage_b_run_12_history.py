"""Immutable run-12 failure; no reconstruction of discarded model output."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).with_name("knowledge_stage_b_run_12")
HASHES = {
    "manifest.json": "7b558c0058be884565544724a5e65a70d99df2fb298bb04031f2a5cd03c121ea",
    "authorization.json": "f30e82aa8da8145104586652190c581b2882e38926c8644906024e27ea20eb71",
    "consumed.json": "2431aea4d502fd627bf22ef4f54c2489fefd450341602c2ce949bfa6bfad4980",
    "journal.jsonl": "ffac99686b316c68e34fe7d3a7ace3cc16409a79ba5c54ec422f6d1ef4f8a3d3",
    "result.json": "8122f04207e4cead37727b49818aeb62618b0139cc6085043bf919a9a2f43ac1",
    "evidence.jsonl": "75ca085ea3f2c921f48fbac325814230f6af5d3687bf70eee13ef396f170fcc9",
    "startup.jsonl": "fadc08a6c85a22eed38f9f8d2d5c81581a97dff0ced67636cbcb9bef52cc9a77",
    "environment.jsonl": "753c395c33e04976b05598a87d25ff00503cf5c174ac6bebd94665ad39d90ddf",
}


def test_original_bytes_tasks_budget_and_terminal_failure():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    assert manifest["frozenHead"] == "05ffadd353eb7299849e1c63893bb18fc6671f66"
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="8", summary="7")
    result = json.loads((ROOT / "result.json").read_bytes())
    assert result["status"] == "failed"
    assert result["totals"] == dict(e2e=2, model=5, search=4, embedding=1, rerank=2, business=0, retry=0, resume=0)
    assert [row["passed"] for row in result["cases"]] == [True, False]
    assert len(result["notExecuted"]) == 8
    assert all(task["status"] == "succeeded" for row in result["cases"] for task in row["modelTasks"])
    assert len((ROOT / "journal.jsonl").read_bytes().splitlines()) == 5
