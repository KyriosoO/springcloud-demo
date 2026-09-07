from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge_corpus_tools.vector_candidate import CandidateError, VectorCandidateResult

RUNNER = Path(__file__).resolve().parents[1] / "scripts/run-policy-vector-candidate.py"


@pytest.mark.parametrize("mode", ["success", "failure", "cancel"])
def test_driver_exclusive_binding_and_finite_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str,
) -> None:
    spec = importlib.util.spec_from_file_location("candidate_runner_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "source_index": "old-policy", "source_uuid": "old-uuid", "mapping_sha256": "a" * 64,
        "source_fingerprint": "b" * 64, "total_count": 3, "policy_count": 2,
        "attachment_count": 1, "candidate_index": "agent-doc-tax-policy-v5-20260907-vector-b1",
    }))
    output = tmp_path / "new-output"
    monkeypatch.setattr(sys, "argv", [str(RUNNER), "--source-binding", str(source),
                                      "--container", "d" * 64, "--output-directory", str(output), "--execute"])
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, stdout=b"" if command[1] == "status" else "c" * 40))
    prep = SimpleNamespace(snapshot_sha256="d" * 64, freeze=lambda: {"finite": True},
                           http_calls=0, text_count=0, max_tokens=16, failure_reason=None)
    monkeypatch.setattr(runner, "LocalVectorPreparation", lambda _: prep)
    calls = 0

    def build(binding: Any, **kwargs: Any) -> VectorCandidateResult:
        nonlocal calls
        calls += 1
        frozen = json.loads((output / "binding.json").read_text())
        assert frozen["spec"]["source_index"] == binding.source_index
        assert frozen["sourceCommit"] == "c" * 40
        assert kwargs["client"].trust_env is False
        if mode == "failure":
            raise CandidateError("bulk_failed", phase="update", seal_status="sealed")
        if mode == "cancel":
            error = KeyboardInterrupt()
            error.add_note("candidate_cleanup:sealed")
            raise error
        return VectorCandidateResult(binding.candidate_index, "new-uuid", 3, 2, 1,
                                     "a" * 64, "b" * 64, "d" * 64, "version", 5)

    monkeypatch.setattr(runner, "build_policy_vector_candidate", build)
    assert runner.main() == {"success": 0, "failure": 1, "cancel": 130}[mode]
    result = json.loads((output / "result.json").read_text())
    assert result["paid"] == result["retry"] == result["resume"] == result["aliasWrites"] == 0
    assert result["status"] == ("built_read_only_unpublished" if mode == "success" else "failed")
    before = (output / "result.json").read_bytes()
    assert runner.main() == 2 and calls == 1
    assert (output / "result.json").read_bytes() == before
    assert "output_exists" in capsys.readouterr().out


def test_token_failure_blocks_clone_with_real_builder() -> None:
    from test_local_vector_preparation import FakeLocal
    from test_vector_candidate import FakeES
    from knowledge_corpus_tools.vector_candidate import build_policy_vector_candidate
    fake_model, fake_es = FakeLocal(), FakeES()
    fake_model.count = 1025
    fake_model.prep.freeze()
    with fake_es.client() as client, pytest.raises(CandidateError):
        build_policy_vector_candidate(fake_es.spec(), client=client, prepare_vectors=fake_model.prep)
    assert fake_model.prep.failure_reason == "tokens_exceeded"
    assert not fake_model.requests and fake_es.target is None
    assert all(method in {"GET", "HEAD"} or (method == "POST" and path.endswith("/_search"))
               for method, path, _ in fake_es.calls)
