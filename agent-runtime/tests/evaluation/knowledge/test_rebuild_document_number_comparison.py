"""Offline protocol/replay tests; synthetic data are not retrieval quality evidence."""
import asyncio
from dataclasses import asdict, replace
import json
import sys

import pytest

from agent_runtime.knowledge.contracts import RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import PathResultKind, PathRetrievalResult
from agent_runtime.knowledge.retrieval.minimal_ranking import domain_pool
from agent_runtime.knowledge.retrieval.minimal_stage import _candidate_set
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.retrieval_helpers import candidate


@pytest.fixture
def draft():
    return p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old-helper", current_helper=b"synthetic-current-helper",
        changed_paths=(p.HELPER,))


def arm(case, *, changed):
    paths = []
    for domain in case.plan.selected_domain_ids:
        for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
            ids = (4, 1, 2) if changed and domain == "tax.policy" and path is RetrievalPath.KEYWORD else (1, 2, 3)
            rows = tuple(candidate(chunk=f"{case.case_id}-{domain}-k{number}", domain=domain,
                rank=rank, content=f"合成测试文本{number}") for rank, number in enumerate(ids, 1))
            paths.append(PathRetrievalResult(kind=PathResultKind.CANDIDATES, logical_domain_id=domain,
                retrieval_profile_id=dict(case.plan.profile_bindings)[domain], path=path,
                profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
                read_policy_version="tax-public-authenticated-v1", candidates=rows))
    sets = tuple(_candidate_set(item, limit=20) for item in paths)
    scores = tuple((domain, tuple((p.CandidateRef.from_candidate(c.candidate),
                                   float(c.candidate.chunk_id[-1]))
                                  for c in domain_pool(sets, domain))) for domain in case.plan.selected_domain_ids)
    return p.ReplayArm(tuple(paths), scores)


def inputs(draft):
    return tuple(p.CaseReplay(case.case_id, arm(case, changed=False), arm(case, changed=True), (0.0,) * 1024)
                 for case in draft.cases)


def test_draft_retains_all_ten_sourced_cases_without_reusing_old_fingerprint(draft):
    view = draft.preview()
    assert len(draft.cases) == 10 and sum(len(c.plan.selected_domain_ids) for c in draft.cases) == 11
    assert view["realExecutionAllowed"] is False and view["runId"] is None
    assert view["plannedRetrievalUpperBounds"] == {"typedSearch": 44, "physicalSearch": 44,
                                                "queryEmbedding": 10, "rerank": 22}
    assert view["actualCorpusSnapshot"].startswith("requires_fresh_snapshot")
    assert "metadata" not in view["plannedRetrievalUpperBounds"]
    assert "physical_http_witness_and_budget" in view["unresolvedBeforeRealExecution"]
    assert all(value == 0 for value in view["forbidden"].values())
    assert view["qualityRules"]["missingBlindLabels"] == "Not assessed"
    assert draft.cases[5].case_id == "UAT-KM-007"
    assert draft.cases[5].plan.selected_domain_ids == ("tax.policy", "tax.law")
    assert "财政" not in p.canonical(view).decode() and "question" not in repr(draft)


@pytest.mark.parametrize("paths", [(), (p.HELPER, "another.java"), ("another.java",)])
def test_non_helper_source_change_cannot_enter_draft(paths):
    with pytest.raises(p.ProtocolError, match="single_variable_unproven"):
        p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
            old_helper=b"old", current_helper=b"new", changed_paths=paths)


def test_fixture_gold_or_threshold_changes_are_rejected():
    raw = (p.ROOT / p.FIXTURE).read_bytes()
    with pytest.raises(p.ProtocolError, match="fixture_drift"):
        p.draft_from_bytes(fixture_raw=raw + b" ", head="f" * 40,
            old_helper=b"old", current_helper=b"new", changed_paths=(p.HELPER,))


@pytest.mark.parametrize("raw", [b"[]", b"", b'{}{}', b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'])
def test_exact_draft_json_rejects_ambiguous_input(raw):
    with pytest.raises(p.ProtocolError):
        p._decode(raw)


def test_repository_source_diff_is_local_exact_and_double_checked(monkeypatch, draft):
    calls = []
    def git(root, *args):
        calls.append(args)
        if args[0] == "branch":
            return b"codex_0915\n"
        if args[0] == "status":
            return b""
        if args[0] == "rev-parse":
            return b"f" * 40 + b"\n"
        if args[0] == "diff":
            assert "config-service/src/main/resources/config" in args
            return p.HELPER.encode() + b"\n"
        if args[1].endswith(p.FIXTURE):
            return (p.ROOT / p.FIXTURE).read_bytes()
        return b"synthetic-old-helper" if args[1].startswith(p.OLD_HEAD) else b"synthetic-current-helper"
    monkeypatch.setattr(p, "_git", git)
    assert p.draft_from_repository() == draft
    assert sum(args[0] == "status" for args in calls) == 2
    assert all(args[0] not in ("fetch", "push", "archive", "checkout") for args in calls)


async def test_actual_production_stage_replay_keyword_may_change_vector_and_law_cannot(draft, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("outbound or child process attempted")
    monkeypatch.setattr(p.subprocess, "run", forbidden)
    result = await p.ReplaySession().evaluate(draft, inputs(draft))
    assert dict(result.simulated_calls) == p.LIMITS
    assert result.real_outbound == 0 and result.quality_conclusion == "Not assessed"
    assert result.evidence_kind == "synthetic_non_live_replay"
    assert len(result.cases) == 10
    first = result.cases[0]
    assert first.baseline.vector == first.candidate.vector
    assert first.baseline.keyword != first.candidate.keyword
    assert first.candidate.final20[0].chunk_id.endswith("k4")
    assert first.baseline.final20[0].chunk_id.endswith("k3")
    assert first.candidate.reranked and first.candidate.fused
    assert len(result.cases[5].candidate.keyword) == 2
    rendered = p.canonical(asdict(result)).decode()
    assert "合成测试文本" not in rendered and "shared_vector" not in rendered
    assert "synthetic-no-outbound" not in rendered and "latency_seconds\":0.0" in rendered


@pytest.mark.parametrize("kind", ["vector", "law_keyword", "snapshot", "metadata", "body", "score", "duplicate_path", "oversize"])
async def test_single_variable_and_binding_drift_fail_closed(draft, kind):
    data = list(inputs(draft))
    index = 5 if kind == "law_keyword" else 0
    current = data[index].current
    paths = list(current.paths)
    if kind in ("vector", "law_keyword"):
        location = 2 if kind == "law_keyword" else 1
        rows = list(paths[location].candidates)
        rows.reverse()
        rows = [replace(row, source_rank=i) for i, row in enumerate(rows, 1)]
        paths[location] = replace(paths[location], candidates=tuple(rows))
    elif kind == "snapshot":
        paths[0] = replace(paths[0], index_snapshot_id="b" * 64)
    elif kind in ("metadata", "body"):
        rows = list(paths[0].candidates)
        target = 1  # k1 is shared with vector and old arm.
        rows[target] = replace(rows[target], title="修改元数据") if kind == "metadata" else replace(
            rows[target], content="不同正文", content_sha256=p.sha256("不同正文".encode()).hexdigest())
        paths[0] = replace(paths[0], candidates=tuple(rows))
    elif kind == "duplicate_path":
        paths[1] = paths[0]
    elif kind == "oversize":
        paths[0] = replace(paths[0], candidates=paths[0].candidates * 7)
    else:
        domain, scores = current.scores[0]
        current = replace(current, scores=((domain, tuple((ref, score + 1) for ref, score in scores)),))
    data[index] = replace(data[index], current=replace(current, paths=tuple(paths)))
    with pytest.raises(p.ReplayError) as failure:
        await p.ReplaySession().evaluate(draft, tuple(data))
    assert len(failure.value.completed) == index
    assert failure.value.case_id == draft.cases[index].case_id
    assert failure.value.unexecuted == p.CASE_IDS[index:]


async def test_no_result_has_no_rerank_and_is_not_quality_success(draft):
    data = []
    for case, replay in zip(draft.cases, inputs(draft), strict=True):
        empty = replace(replay.old, paths=tuple(replace(row, kind=PathResultKind.NO_RESULT, candidates=())
                                               for row in replay.old.paths), scores=())
        data.append(replace(replay, old=empty, current=empty))
    result = await p.ReplaySession().evaluate(draft, tuple(data))
    assert dict(result.simulated_calls) == {"typedSearch": 44, "queryEmbedding": 10, "rerank": 0}
    assert all(not row.candidate.final20 for row in result.cases)
    assert result.quality_conclusion == "Not assessed"


async def test_metrics_cover_every_stage_and_never_convert_sources_to_precision(draft):
    result = await p.ReplaySession().evaluate(draft, inputs(draft))
    metrics = p.replay_metrics(draft, result)
    assert metrics["simulatedMacroRecallAt20"] == {"old": 0.0, "current": 0.0}
    assert set(metrics["cases"][0]["simulatedNecessarySourceCoverage"]["old"]) == {
        "keyword", "vector", "RRF", "rerank", "final20"}
    assert metrics["precisionAt20"] is None and metrics["medianLatencyRatio"] is None
    assert metrics["qualityConclusion"] == "Not assessed"
    assert not any(metrics[key] for key in ("realExecutionAllowed", "adoptionAllowed", "releaseAllowed"))
    # Synthetic arithmetic only: no corpus text, live query, or real verdict.
    first = replace(result.cases[0], candidate=replace(result.cases[0].candidate,
                                                     final20=draft.cases[0].necessary_sources))
    modified = replace(result, cases=(first, *result.cases[1:]))
    assert p.replay_metrics(draft, modified)["simulatedMacroRecallAt20"]["current"] == 0.1
    assert p.replay_metrics(draft, modified)["qualityConclusion"] == "Not assessed"


@pytest.mark.parametrize("change", ["partial", "foreign_hash", "wrong_kind", "quality_claim", "outbound"])
async def test_metric_input_cannot_be_partial_foreign_or_promoted_to_real(draft, change):
    result = await p.ReplaySession().evaluate(draft, inputs(draft))
    changes = {"partial": {"cases": result.cases[:-1]}, "foreign_hash": {"draft_sha256": "0" * 64},
               "wrong_kind": {"evidence_kind": "real_readonly"},
               "quality_claim": {"quality_conclusion": "Passed"}, "outbound": {"real_outbound": 1}}
    with pytest.raises(p.ProtocolError, match="metric_binding_invalid"):
        p.replay_metrics(draft, replace(result, **changes[change]))


async def test_rerank_failure_charges_attempt_stops_and_session_cannot_resume(draft):
    data = list(inputs(draft))
    data[0] = replace(data[0], old=replace(data[0].old, scores=()))
    session = p.ReplaySession()
    with pytest.raises(p.ReplayError) as failure:
        await session.evaluate(draft, tuple(data))
    assert failure.value.counts == {"typedSearch": 2, "queryEmbedding": 1, "rerank": 1}
    assert failure.value.completed == ()
    with pytest.raises(p.ProtocolError, match="already_attempted"):
        await session.evaluate(draft, inputs(draft))


async def test_cancellation_does_not_leave_stage_children_or_continue_cases(draft, monkeypatch):
    original = p._Ports.search
    async def cancel(self, **kwargs):
        await original(self, **kwargs)
        raise asyncio.CancelledError
    monkeypatch.setattr(p._Ports, "search", cancel)
    before = asyncio.all_tasks()
    with pytest.raises(p.ReplayError, match="replay_cancelled"):
        await p.ReplaySession().evaluate(draft, inputs(draft))
    assert asyncio.all_tasks() == before


@pytest.mark.parametrize("kind,limit", p.LIMITS.items())
def test_each_budget_exact_limit_and_forbidden_kind_are_fail_closed(kind, limit):
    budget = p._Budget()
    for _ in range(limit):
        budget.reserve(kind)
    with pytest.raises(p.ProtocolError, match="budget_exceeded"):
        budget.reserve(kind)
    assert budget.counts[kind] == limit
    with pytest.raises(p.ProtocolError):
        budget.reserve("aliasWrites")


@pytest.mark.parametrize("mutation", ["missing", "repeat", "vector", "nan"])
async def test_no_subset_repeated_case_or_invalid_shared_vector(draft, mutation):
    data = list(inputs(draft))
    if mutation == "missing":
        data.pop()
    elif mutation == "repeat":
        data[1] = data[0]
    else:
        data[0] = replace(data[0], shared_vector=(0.0,) * 1023 if mutation == "vector"
                          else (float("nan"),) * 1024)
    with pytest.raises(p.ProtocolError):
        await p.ReplaySession().evaluate(draft, tuple(data))


def test_cli_has_no_live_execute_mode(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["private-comparison", "execute"])
    with pytest.raises(SystemExit) as failure:
        p.main()
    assert failure.value.code == 2


def test_cli_preview_is_not_authorization_or_live_result(monkeypatch, draft, capsys):
    monkeypatch.setattr(sys, "argv", ["private-comparison", "--preview"])
    monkeypatch.setattr(p, "draft_from_repository", lambda: draft)
    p.main()
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "non_live_only" and value["realExecutionAllowed"] is False
    assert "authorization" not in value and "actualCounts" not in value
