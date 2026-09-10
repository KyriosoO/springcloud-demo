"""Explicit historical inputs shared by evaluation and system harness tests.

No autouse fixtures: current production/configuration tests never opt in.
"""
import hashlib
import io
import json
import subprocess
from types import SimpleNamespace

import pytest


@pytest.fixture
def source_replay_frozen_profile(monkeypatch):
    from tests.system_e2e import knowledge_evidence_source_replay_v1 as replay

    source = subprocess.run([
        "git", "show", "6306c050388f5b1d2b6f99fddf8364674b1cd8f0:"
        "es-query-service/src/main/resources/application-knowledge-live.yml",
    ], cwd=replay.REPO, capture_output=True, timeout=10, check=True).stdout
    prepared = json.loads(replay.SAVED.read_bytes().splitlines()[0])
    assert hashlib.sha256(source).hexdigest() == prepared["artifactHashes"][
        "es-query-service/target/classes/application-knowledge-live.yml"]
    # In-memory read-only fixture: do not overwrite the current file, weaken
    # load_inputs hash checks, or change the already-consumed launcher.
    monkeypatch.setattr(replay, "PROFILE", SimpleNamespace(read_bytes=lambda: source))
    return source


@pytest.fixture
def window_probe_frozen_inputs(source_replay_frozen_profile, monkeypatch):
    from tests.system_e2e import knowledge_rerank_window_probe_v1 as probe

    source = subprocess.run([
        "git", "show", "88c4fbea63523a0b793dd05253062e74f4d6cc0d:"
        "agent-runtime/tests/evaluation/knowledge/retrieval_relevance.review.v1.jsonl",
    ], cwd=probe.REPO, capture_output=True, timeout=10, check=True).stdout
    assert hashlib.sha256(source).hexdigest() == probe.REVIEW_SHA
    assert probe.review.PATH.read_bytes().startswith(source)
    monkeypatch.setattr(probe.review, "PATH", SimpleNamespace(
        read_bytes=lambda: source, open=lambda mode: io.BytesIO(source)))
