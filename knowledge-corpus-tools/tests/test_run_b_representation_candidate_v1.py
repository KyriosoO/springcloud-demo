from __future__ import annotations

import runpy
from pathlib import Path

import httpx
import pytest

from knowledge_corpus_tools.b_candidate_freeze_v1 import BFreezeError


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run-b-representation-candidate-v1.py"


def test_cli_transport_refuses_non_loopback_or_wrong_service_before_network() -> None:
    namespace = runpy.run_path(str(SCRIPT))
    transport = namespace["LimitedLocalTransport"](port=8908, maximum=1)
    try:
        for url in ("https://127.0.0.1:8908/embed",
                    "http://example.org:8908/embed",
                    "http://127.0.0.1:9200/embed",
                    "http://127.0.0.1:8908/other"):
            with pytest.raises(BFreezeError, match="budget_invalid"):
                transport.handle_request(httpx.Request("POST", url))
        with pytest.raises(BFreezeError, match="budget_invalid"):
            transport.handle_request(httpx.Request("GET", "http://127.0.0.1:8908/embed"))
        assert transport.calls == 0
    finally:
        transport.close()


def test_mapping_transport_refuses_writes_and_other_indices() -> None:
    namespace = runpy.run_path(str(SCRIPT))
    transport = namespace["ReadOnlyMappingTransport"](
        index_name="agent-doc-candidate", maximum=2)
    try:
        for method, url in (
            ("POST", "http://127.0.0.1:9200/agent-doc-candidate/_bulk"),
            ("PUT", "http://127.0.0.1:9200/agent-doc-candidate/_settings"),
            ("GET", "http://127.0.0.1:9200/other-index"),
            ("POST", "http://127.0.0.1:9200/_aliases"),
        ):
            with pytest.raises(BFreezeError, match="budget_invalid"):
                transport.handle_request(httpx.Request(method, url))
        assert transport.calls == 0
    finally:
        transport.close()


def test_git_probe_is_read_only_and_uses_repository_root(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    calls: list[tuple[str, ...]] = []

    class Result:
        def __init__(self, value: str) -> None:
            self.stdout = value
            self.returncode = 0

    def fake_run(args: list[str], **kwargs: object) -> Result:
        assert kwargs["cwd"] == namespace["ROOT"]
        calls.append(tuple(args))
        return Result({"branch": "codex_0915", "rev-parse": "a" * 40,
                       "status": ""}[args[1]])

    monkeypatch.setattr(namespace["subprocess"], "run", fake_run)
    state = namespace["_git_state"]()
    assert (state.branch, state.head, state.tracked_clean) == (
        "codex_0915", "a" * 40, True)
    assert calls == [
        ("git", "branch", "--show-current"),
        ("git", "rev-parse", "HEAD"),
        ("git", "status", "--porcelain", "--untracked-files=all", "--",
         "knowledge-corpus-tools/src",
         "knowledge-corpus-tools/scripts/run-b-representation-candidate-v1.py",
         "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"),
    ]


def test_git_probe_rejects_untracked_execution_source(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = runpy.run_path(str(SCRIPT))

    class Result:
        returncode = 0

        def __init__(self, value: str) -> None:
            self.stdout = value

    def fake_run(args: list[str], **_: object) -> Result:
        return Result({"branch": "codex_0915", "rev-parse": "a" * 40,
                       "status": "?? knowledge-corpus-tools/src/untracked.py\n"}[args[1]])

    monkeypatch.setattr(namespace["subprocess"], "run", fake_run)
    assert namespace["_git_state"]().tracked_clean is False
