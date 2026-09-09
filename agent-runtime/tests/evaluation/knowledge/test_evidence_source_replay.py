"""Fake-only verification of the bounded real-source audit, no live opt-in."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import sys

import httpx
import pytest
import yaml

from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement, KnowledgeRequirementKind
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressDisposition
from tests.evaluation.knowledge.retrieval_benchmark_dataset import Case, Dataset, Source
from tests.evidence_helpers import synthetic_catalog
from tests.system_e2e import knowledge_evidence_source_replay_v1 as replay


def fixture():
    sources = {key: {"documentId": "d1", "chunkId": key, "title": "合成标题", "content": text,
        "sourceUrl": None, "documentNo": None, "writtenDate": None, "materialType": "tax_policy",
        "aclRef": "policy-doc-v1", "channel": "curated"} for key, text in (("c1", "合成必要原文"), ("c2", "合成可选原文"))}
    ids = [{"chunkId": key, "sha256": replay.digest(s["content"].encode())} for key, s in sources.items()]
    case = Case("KRB-T", "development", "增值税政策的规定是什么？", ("tax.policy",),
        (KnowledgeEvidenceRequirement(requirement_id="r1", domain_id="tax.policy",
            kind=KnowledgeRequirementKind.RULE, focus="增值税政策的规定"),), ("required",))
    dataset = Dataset("b" * 64, "c" * 64,
        (Source("required", "c1", ids[0]["sha256"], "tax.policy", "synthetic", ("必要原文",)),), (case,))
    rows = [{"caseId": case.id, "event": "retrieval_stage", "stage": "path", "domain": "tax.policy",
             "path": p, "status": "candidates", "candidates": ids} for p in ("keyword", "vector")]
    rows += [{"caseId": case.id, "event": "retrieval_stage", "stage": "rerank", "ordinal": 1,
              "candidates": [{**ids[0], "score": 0.9}, {**ids[1], "score": 0.1}]},
             {"caseId": case.id, "event": "case", "ranked": [
                 {**ids[0], "rank": 1, "requirementIds": ["r1"]}, {**ids[1], "rank": 2, "requirementIds": []}]}]
    profiles = yaml.safe_load(replay.PROFILE.read_bytes())["es"]["query"]["knowledge"]["profiles"]
    return case, dataset, rows, sources, {"policySnapshotId": "a" * 64}, profiles


@pytest.mark.asyncio
async def test_real_shape_replay_uses_source_bytes_policy_and_first_scores():
    case, dataset, rows, sources, binding, profiles = fixture()
    original = deepcopy((rows, sources))
    value, _ = await replay.replay_case(case, rows, sources, binding, profiles)
    assert value.batch.candidates[0].candidate.content == sources["c1"]["content"]
    old = replay.evaluate(value, replay.base.DeterministicEvidenceSelector(), synthetic_catalog(), case, dataset)
    new = replay.evaluate(value, ScoreAwareEvidenceSelector(), synthetic_catalog(), case, dataset)
    assert len(old["evidence"]) == 2 and len(new["evidence"]) == 1
    assert new["requiredSourcesPreserved"] and new["sufficient"] and new["policyAllowed"]
    assert 0 < new["payloadBytes"] < old["payloadBytes"] <= 32768
    assert new["metrics"]["precision_at_k"] is new["metrics"]["ndcg_at_k"] is None
    assert (rows, sources) == original
    assert "合成" not in json.dumps(new, ensure_ascii=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["rank", "hash", "domain", "scores", "date", "metadata_type"])
async def test_source_or_replay_drift_fails_before_selection(change):
    case, _, rows, sources, binding, profiles = fixture()
    if change == "rank": rows[-1]["ranked"].reverse()
    if change == "hash": sources["c2"]["content"] = "changed low-score body"
    if change == "domain": sources["c2"]["channel"] = "法律"
    if change == "scores": rows[2]["candidates"].pop()
    if change == "date": sources["c2"]["writtenDate"] = "not-date"
    if change == "metadata_type": sources["c2"]["materialType"] = 3
    with pytest.raises(ValueError):
        await replay.replay_case(case, rows, sources, binding, profiles)


@pytest.mark.asyncio
async def test_denied_and_missing_policy_do_not_become_success():
    case, dataset, rows, sources, binding, profiles = fixture()
    value, _ = await replay.replay_case(case, rows, sources, binding, profiles)
    denied = replay.evaluate(value, ScoreAwareEvidenceSelector(),
        synthetic_catalog(disposition=KnowledgeEgressDisposition.DENY), case, dataset)
    assert not denied["policyAllowed"] and not denied["requiredSourcesPreserved"] and denied["payloadBytes"] == 0
    changed = replace(value, batch=replace(value.batch, candidates=tuple(replace(c,
        candidate=replace(c.candidate, policy_ref="unclassified")) for c in value.batch.candidates)))
    missing = replay.evaluate(changed, ScoreAwareEvidenceSelector(), synthetic_catalog(), case, dataset)
    assert not missing["policyAllowed"] and not missing["requiredSourcesPreserved"]


def response():
    _, _, _, sources, _, _ = fixture()
    pool = {key: (replay.digest(s["content"].encode()), "tax.policy") for key, s in sources.items()}
    value = {"timed_out": False, "_shards": {"failed": 0}, "hits": {
        "total": {"value": 2, "relation": "eq"}, "hits": [{"_source": s} for s in sources.values()]}}
    return value, pool


@pytest.mark.parametrize("change", ["timeout", "shards", "total", "duplicate", "unknown", "body", "metadata", "missing"])
def test_partial_or_changed_source_response_rejected(change):
    value, pool = response()
    if change == "timeout": value["timed_out"] = True
    if change == "shards": value["_shards"]["failed"] = 1
    if change == "total": value["hits"]["total"]["relation"] = "gte"
    if change == "duplicate": value["hits"]["hits"][1] = deepcopy(value["hits"]["hits"][0])
    if change == "unknown": value["hits"]["hits"][0]["_source"]["secret"] = "never save"
    if change == "body": value["hits"]["hits"][0]["_source"]["content"] += "modified"
    if change == "metadata": value["hits"]["hits"][0]["_source"]["title"] = ["invalid"]
    if change == "missing": value["hits"]["hits"].pop()
    with pytest.raises(replay.ReplayError): replay.validate_hits(value, list(pool), pool)


def test_source_reader_real_bounded_http_and_no_retry(monkeypatch):
    value, pool = response()
    requests = []

    def send(request):
        requests.append(request)
        assert str(request.url) == "http://127.0.0.1:9200/fake-index/_search" and request.method == "POST"
        assert not request.headers.get("authorization")
        assert json.loads(request.content)["query"] == {"terms": {"chunkId": ["c1", "c2"]}}
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value).encode()))

    client = httpx.Client
    monkeypatch.setattr(replay.httpx, "Client", lambda **kw: client(**kw, transport=httpx.MockTransport(send)))
    reader = replay.SourceReader(replay.base.load_support(), {"expectedIndexName": "fake-index"}, 1)
    assert set(reader.read_pool(pool)) == set(pool)
    with pytest.raises(replay.ReplayError, match="source_read_budget"): reader.read_pool(pool)
    assert reader.reads == len(requests) == 1


def test_snapshot_budget_counts_attempts_and_forbids_mutation():
    calls = []
    def fail(*args):
        calls.append(args)
        raise TimeoutError("never serialize")
    checker = replay.SnapshotReader(SimpleNamespace(bounded_request=fail),
        {"readAlias": "fake-alias", "expectedIndexName": "fake-index"})
    with pytest.raises(TimeoutError): checker.bounded_request(None, "GET", "/fake-index/_mapping")
    with pytest.raises(replay.ReplayError): checker.bounded_request(None, "POST", "/fake-index/_mapping")
    assert checker.reads == len(calls) == 1


def test_frozen_inputs_and_scope_are_bound_before_reads():
    rows, dataset, pool, _ = replay.load_inputs()
    assert len(pool) == 504 and len(dataset.cases) == 24
    assert rows[0]["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    assert "offline_source_replay_not_fresh_read_authorization" in replay.LIMITATIONS
    assert "ungraded_relevance" in replay.LIMITATIONS


@pytest.mark.parametrize("error", [replay.ReplayError("source_hash_changed"),
    replay.ReplayError("untrusted source text"), ValueError("untrusted source text")])
def test_terminal_failure_is_finite_append_only_and_cannot_resume(monkeypatch, tmp_path, capsys, error):
    target = tmp_path / "result.jsonl"
    monkeypatch.setattr(replay, "RESULT", target)
    monkeypatch.setattr(sys, "argv", ["replay", "--execute"])
    monkeypatch.setattr(replay, "current_head", lambda: "a" * 40)
    def fail(): raise error
    monkeypatch.setattr(replay, "load_inputs", fail)
    assert replay.main() == 1
    raw = target.read_bytes()
    result = json.loads(raw)
    assert result["status"] == "failed" and result["casesMeasured"] == 0
    assert result["sourceReads"] == result["snapshotReads"] == result["modelCalls"] == 0
    assert result["failureReason"] == ("source_hash_changed" if str(error) == "source_hash_changed" else "execution_failed")
    assert "untrusted source text" not in raw.decode() + capsys.readouterr().out
    with pytest.raises(FileExistsError): replay.main()
    assert target.read_bytes() == raw


@pytest.mark.parametrize("kind", ["timeout", "oversized", "encoding", "http_failure"])
def test_http_failure_consumes_one_attempt_without_retry(monkeypatch, kind):
    _, pool = response()
    calls = []
    def send(request):
        calls.append(request)
        if kind == "timeout": raise httpx.ReadTimeout("raw text must not escape", request=request)
        if kind == "oversized": return httpx.Response(200, stream=httpx.ByteStream(b"x" * (2 * 1024 * 1024 + 1)))
        if kind == "encoding": return httpx.Response(200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"x"))
        return httpx.Response(503, stream=httpx.ByteStream(b"raw error"))
    client = httpx.Client
    monkeypatch.setattr(replay.httpx, "Client", lambda **kw: client(**kw, transport=httpx.MockTransport(send)))
    reader = replay.SourceReader(replay.base.load_support(), {"expectedIndexName": "fake-index"}, 1)
    with pytest.raises((ValueError, httpx.HTTPError)): reader.read_pool(pool)
    assert reader.reads == len(calls) == 1


@pytest.mark.asyncio
async def test_complete_fake_run_rechecks_sources_and_only_emits_finite_projection(monkeypatch, tmp_path, capsys):
    case, dataset, rows, sources, binding, profiles = fixture()
    binding.update(expectedIndexName="fake-index", readAlias="fake-read")
    value, _ = await replay.replay_case(case, rows, sources, binding, profiles)
    catalog = synthetic_catalog()
    old = replay.evaluate(value, replay.base.DeterministicEvidenceSelector(), catalog, case, dataset)
    rows[-1].update(evidence=old["evidence"], selectionSufficient=True, policyAllowed=True)
    rows.insert(0, {"localModelContainers": {}, "rerankInputVersion": "synthetic"})
    pool = {k: (replay.digest(s["content"].encode()), "tax.policy") for k, s in sources.items()}
    target = tmp_path / "finite.jsonl"
    monkeypatch.setattr(replay, "RESULT", target)
    monkeypatch.setattr(sys, "argv", ["replay", "--execute"])
    monkeypatch.setattr(replay, "current_head", lambda: "a" * 40)
    monkeypatch.setattr(replay, "load_inputs", lambda: (rows, dataset, pool, profiles))
    monkeypatch.setattr(replay.base, "load_support", lambda: SimpleNamespace(
        checked_bytes=lambda *args: replay.canonical(binding)))
    monkeypatch.setattr(replay.base, "CATALOG_SHA", catalog.snapshot.source_sha256)
    monkeypatch.setattr(replay.base.KnowledgeEgressPolicyCatalog, "load_current_resource", lambda: catalog)
    def no_models(): raise AssertionError("saved score replay must not depend on running BGE")
    monkeypatch.setattr(replay.base, "local_models", no_models)
    snapshots = []
    monkeypatch.setattr(replay.base, "check_index", lambda *args: snapshots.append(True))
    def read(reader, _):
        reader.reads += 1
        return deepcopy(sources)
    monkeypatch.setattr(replay.SourceReader, "read_pool", read)
    # Run the synchronous launcher outside this test's existing event loop.
    import asyncio
    assert await asyncio.to_thread(replay.main) == 0
    output = target.read_text()
    records = [json.loads(line) for line in output.splitlines()]
    assert [r["event"] for r in records] == ["prepared", "case", "terminal"]
    assert records[-1]["sourceReads"] == len(snapshots) == 2
    assert records[-1]["casesMeasured"] == records[-1]["requiredSourcesPreserved"] == 1
    assert records[1]["candidate"]["payloadBytes"] < records[1]["legacy"]["payloadBytes"]
    assert "合成" not in output + capsys.readouterr().out
