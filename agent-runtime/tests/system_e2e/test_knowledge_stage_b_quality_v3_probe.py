"""Diagnostic tests never execute a live launcher or read model credentials."""
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from tests.evidence_helpers import synthetic_catalog
from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressDisposition
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as probe


def test_frozen_plans_are_current_finite_and_do_not_claim_clarification_or_summary():
    plans = [probe.plan_for(spec)[1] for spec in probe.SPECIFICATIONS]
    assert len(plans) == 8 and probe.LIMITS == {"search": 22, "embedding": 11, "rerank": 18}
    assert all(p.quality_version == probe.KNOWLEDGE_QUALITY_VERSION_V3 for p in plans)
    assert all(p.evidence_requirements and len(p.evidence_requirements) <= 4 for p in plans)
    assert {s[0] for s in probe.SPECIFICATIONS}.isdisjoint({"UAT-KB-001", "UAT-KB-005"})
    assert all(i.candidate_limit == 20 for p in plans for i in p.items)
    assert all("requiredGold" not in probe.asdict(p) for p in plans)


@pytest.mark.asyncio
@pytest.mark.parametrize("url,method,headers", [
    ("http://127.0.0.1:8909/rerank", "POST", {"Authorization": "private-test-token"}),
    ("http://127.0.0.1:8908/embed", "POST", {"Authorization": "private-test-token"}),
    ("https://api.deepseek.com/chat/completions", "POST", {}),
    ("http://127.0.0.1:19201/es/search", "POST", {}),
    ("http://127.0.0.1:9200/_search", "POST", {}),
    ("http://127.0.0.1:9210/employees/es/search", "POST", {}),
    ("http://127.0.0.1:8908/embed", "GET", {}),
])
async def test_outbound_guard_refuses_wrong_endpoint_or_bge_credentials(url, method, headers):
    budget = probe.Budget()
    with pytest.raises(ValueError, match="outbound_rejected"):
        await budget.request(httpx.Request(method, url, headers=headers))
    assert budget.stopped and not any(budget.total.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,url", [("search", "http://127.0.0.1:19201/es/knowledge/search"),
                                     ("embedding", "http://127.0.0.1:8908/embed"),
                                     ("rerank", "http://127.0.0.1:8909/rerank")])
@pytest.mark.parametrize("which", ["total", "current"])
async def test_budget_checked_before_attempt(kind, url, which):
    budget = probe.Budget()
    getattr(budget, which)[kind] = (probe.LIMITS if which == "total" else probe.PER_CASE)[kind]
    before = dict(budget.total), dict(budget.current)
    with pytest.raises(ValueError):
        await budget.request(httpx.Request("POST", url))
    assert before == (budget.total, budget.current)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "forbidden", "snapshot", "rerank", "policy"])
async def test_real_stage_and_selector_on_mock_http_preserve_failures_and_do_not_emit_body(monkeypatch, fault):
    monkeypatch.setattr(probe, "SPECIFICATIONS", probe.SPECIFICATIONS[:1])
    catalog = synthetic_catalog(disposition=KnowledgeEgressDisposition.DENY if fault == "policy"
                                else KnowledgeEgressDisposition.ALLOW_MINIMAL)
    monkeypatch.setattr(probe, "CATALOG_SHA", catalog.snapshot.source_sha256)
    monkeypatch.setattr(probe, "KnowledgeEgressPolicyCatalog", SimpleNamespace(load_current_resource=lambda: catalog))
    content = "公开合成增值税依据，不是真实知识正文"
    digest = hashlib.sha256(content.encode()).hexdigest()
    gold = {name: {"chunk": "synthetic", "sha256": digest, "clause": content} for name in ("lodging", "living")}
    monkeypatch.setattr(probe, "GOLD", gold)
    seen, clients, events = [], [], []

    def reply(status, body):
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(body).encode()),
                              headers={"Content-Type": "application/json"})

    def handle(request):
        seen.append((request.url.path, request.headers.get("Authorization")))
        body = json.loads(request.content)
        if request.url.path == "/embed":
            return reply(200, {"dim": 1024, "vectors": [[0.1] * 1024]})
        if request.url.path == "/rerank":
            return reply(503 if fault == "rerank" else 200, {"model": "BAAI/bge-reranker-v2-m3",
                "results": [{"index": i, "text": text, "score": 0.5} for i, text in enumerate(body["documents"])]})
        assert request.url.path == "/es/knowledge/search"
        result = {"schemaVersion": 1, "logicalDomainId": "tax.policy", "retrievalProfileId": "tax-policy-v1",
            "path": body["path"], "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": ("b" if fault == "snapshot" else "a") * 64,
            "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
            "candidates": [{"documentId": "d1", "chunkId": "synthetic", "logicalDomainId": "tax.policy",
                "title": "合成测试标题", "content": content, "sourceUrl": None, "documentNumber": None,
                "writtenDate": None, "materialType": "tax_policy", "sourceRank": 1, "contentSha256": digest, "policyRef": "policy-doc-v1"}]}
        return reply(403 if fault == "forbidden" else 200, {} if fault == "forbidden" else result)

    def factory(origin):
        client = httpx.AsyncClient(base_url=origin, transport=httpx.MockTransport(handle), trust_env=False)
        clients.append(client)
        return client

    budget = probe.Budget()
    if fault in ("forbidden", "snapshot", "rerank"):
        with pytest.raises(ValueError, match="retrieval_failed"):
            await probe.diagnose({"policySnapshotId": "a" * 64}, "private-test-token", events.append, budget, client_factory=factory)
        assert events[-1]["status"] == "retrieval_failed"
    else:
        result = await probe.diagnose({"policySnapshotId": "a" * 64}, "private-test-token", events.append, budget, client_factory=factory)
        assert result == {"casesMeasured": 1, "casesWithRequiredSources": 0 if fault == "policy" else 1}
        assert events[-1]["selectionSufficient"] and events[-1]["policyAllowed"] == (fault != "policy")
        assert budget.total == {"search": 2, "embedding": 1, "rerank": 2}
        assert any(r["event"] == "retrieval_stage" and r["stage"] == "fusion" for r in events)
    assert clients and all(c.is_closed for c in clients)
    encoded = json.dumps(events, ensure_ascii=False)
    assert content not in encoded and "private-test-token" not in encoded and "合成测试标题" not in encoded
    assert not any(auth for path, auth in seen if path != "/es/knowledge/search")
    if fault in ("forbidden", "snapshot"):
        assert budget.total["rerank"] == 0


def test_append_result_rejects_large_and_nonfinite_and_cannot_replace(tmp_path):
    path = tmp_path / "result.jsonl"
    with path.open("xb") as stream:
        probe.emit_line(stream, {"event": "prepared"})
        with pytest.raises(ValueError): probe.emit_line(stream, {"score": float("nan")})
        with pytest.raises(ValueError): probe.emit_line(stream, {"value": "x" * 65537})
    before = path.read_bytes()
    with pytest.raises(FileExistsError): path.open("xb")
    assert path.read_bytes() == before and len(before.splitlines()) == 1


def test_helper_and_catalog_are_exact_frozen_sources():
    support = probe.load_support()
    assert support.BINDING_SHA == probe.BINDING_SHA and support.CATALOG_SHA == probe.CATALOG_SHA
    assert probe.KnowledgeEgressPolicyCatalog.load_current_resource().snapshot.source_sha256 == probe.CATALOG_SHA


@pytest.mark.parametrize("value", ["bad", "a " + "b" * 64 + " true", "a" * 64 + " sha256:" + "b" * 64 + " false"])
def test_model_identity_rejects_wrong_shape_and_stopped_container(monkeypatch, value):
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *a, **k: value)
    with pytest.raises(ValueError, match="local_models_invalid"):
        probe.local_models()


def test_model_identity_is_only_container_and_image_not_environment(monkeypatch):
    calls = []
    def inspect(command, **kwargs):
        calls.append(command)
        return "a" * 64 + " sha256:" + "b" * 64 + " true"
    monkeypatch.setattr(probe.subprocess, "check_output", inspect)
    assert len(probe.local_models()) == 2
    assert all(c[0:3] == ["docker", "inspect", "--format"] and c[3] == "{{.Id}} {{.Image}} {{.State.Running}}" for c in calls)


def test_failed_real_probe_is_immutable_not_uat_and_stays_bound_to_frozen_source():
    path = probe.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-probe-20260908-01.jsonl"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "7387ba9450d46529c48434592d09a2b846cfb4c5532b922ec2a6b25512c378b6"
    rows = [json.loads(line) for line in raw.splitlines()]
    prepared, terminal = rows[0], rows[-1]
    frozen = probe.subprocess.check_output(["git", "show", prepared["head"] + ":agent-runtime/tests/system_e2e/knowledge_stage_b_quality_v3_probe.py"], cwd=probe.REPO)
    assert hashlib.sha256(frozen).hexdigest() == prepared["scriptSha256"]
    cases = [row for row in rows if row["event"] == "case"]
    assert len(cases) == 1 and cases[0]["caseId"] == "UAT-KB-015a"
    assert cases[0]["status"] == "retrieval_failed" and cases[0]["stageCode"] == "rerank_timeout"
    assert terminal["status"] == "failed" and terminal["counts"] == {"search": 2, "embedding": 1, "rerank": 1}
    assert all(terminal[k] == 0 for k in ("modelCalls", "businessCalls", "indexWrites", "retry", "resume"))
    assert all(terminal[k] is True for k in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    assert "not_functional_or_effectiveness_uat" in terminal["limitations"]


def test_post_fix_measurement_preserves_all_cases_and_does_not_reclassify_missing_sources():
    path = probe.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-post-warmup-20260908-01.jsonl"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "923697c6a8314e8f4a64d83f307e91df7bc308f7240c70007f5589ce1a95af5f"
    rows = [json.loads(line) for line in raw.splitlines()]
    prepared, terminal = rows[0], rows[-1]
    frozen = probe.subprocess.check_output(["git", "show", prepared["head"] + ":agent-runtime/tests/system_e2e/knowledge_stage_b_quality_v3_probe.py"], cwd=probe.REPO)
    assert hashlib.sha256(frozen).hexdigest() == prepared["scriptSha256"]
    assert prepared["head"] == "4ba5d5ed6ee3fdc7b687af262e0df01545c93bd9"
    assert terminal["status"] == "measured" and terminal["casesMeasured"] == 8
    assert terminal["counts"] == {"search": 22, "embedding": 11, "rerank": 18}
    assert all(terminal[k] == 0 for k in ("modelCalls", "businessCalls", "indexWrites", "retry", "resume"))
    assert all(terminal[k] is True for k in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    cases = [row for row in rows if row["event"] == "case"]
    assert [row["caseId"] for row in cases] == prepared["caseIds"] == [spec[0] for spec in probe.SPECIFICATIONS]
    assert all(row["status"] == "measured" for row in cases)
    missing = {(row["caseId"], label) for row in cases for label, value in row["requiredSources"].items()
               if not value["allowedOriginalClause"]}
    assert missing == {("UAT-KB-003", "rent"), ("UAT-KB-006", "historical_rate")}
    assert terminal["casesWithRequiredSources"] == sum(
        all(value["allowedOriginalClause"] for value in row["requiredSources"].values()) for row in cases) == 6
    assert all(row["selectionSufficient"] and row["policyAllowed"] for row in cases)
    # Structural sufficiency is not semantic proof and must not erase the two gaps.
    assert "not_functional_or_effectiveness_uat" in terminal["limitations"]


def test_visibility_record_separates_observed_loss_from_unproven_optimization():
    value = json.loads((probe.REPO / "agent-runtime/tests/system_e2e/knowledge_stage_b_rerank_visibility.v1.json").read_text())
    assert value["kind"] == "local_rerank_diagnosis_not_uat"
    assert value["recordedFrom"] == "bounded_console_outputs_and_immutable_probe"
    source = probe.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-post-warmup-20260908-01.jsonl"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == value["probeSha256"]
    frozen = probe.subprocess.check_output(["git", "show", value["sourceHead"] + ":serviceCenter/warmup-knowledge-reranker.py"], cwd=probe.REPO)
    assert hashlib.sha256(frozen).hexdigest() == value["startupCheck"]["scriptSha256"]
    events = list(map(json.loads, source.read_bytes().splitlines()))
    cases = {row["caseId"]: row for row in events if row["event"] == "case"}
    for row in value["visibilityInspection"]["rows"]:
        assert row["clauseVisibleAt512"] and 0 <= row["clauseStart"] < row["clauseEnd"] <= row["visibleContentEnd"] <= row["contentCharacters"]
        expected = cases[row["caseId"]]["requiredSources"][row["sourceLabel"]]
        assert expected["pathRanks"] and expected["finalRank"] is None and expected["evidenceRank"] is None
        assert probe.GOLD[row["sourceLabel"]]["sha256"] == row["sha256"]
        ranks = []
        for stage in events:
            if stage.get("stage") != "rerank" or stage["caseId"] != row["caseId"]:
                continue
            ordered = sorted(stage["candidates"], key=lambda item: -item["score"])
            target = next(item for item in ordered if item["chunkId"] == row["chunkId"])
            assert sum(item["score"] == target["score"] for item in ordered) == 1
            ranks.append(1 + ordered.index(target))
        assert ranks == row["rerankRanksByRequirement"]
    assert value["findings"]["sourcesLostBeforeFinalWindow"]
    assert not any(value["findings"][key] for key in ("metadataContextImprovementProven", "semanticEquivalentEvidenceAudited",
                                                    "rewriteOrSummaryMeasured", "uatPassed"))
