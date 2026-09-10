"""No real network/credentials: one-summary lifecycle and current-root rejection."""
import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement, KnowledgeRequirementKind
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.integration.knowledge.test_requirement_runtime_composition import Clients, CONTENTS, FOCUSES, QUESTION
from tests.system_e2e import knowledge_summary_diagnostic_v1 as diagnostic
from tests.system_e2e.test_knowledge_model_failure_probe_v1 import wire


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,reason,status", [
    (None, None, "success"), ("insufficient", None, "no_result"),
    ("coverage", "coverage_ids_invalid", "downstream_failure"),
    ("quote", "quote_not_substring", "downstream_failure"),
    ("json", None, "downstream_failure"), ("timeout", None, "timeout"),
    ("denied", None, "forbidden"), ("policy", None, "model_egress_denied"),
    ("partial", None, "downstream_failure"),
])
async def test_current_root_real_transport_decoder_and_postvalidation_finite(
    tmp_path, monkeypatch, caplog, fault, reason, status,
):
    clients = Clients(fault=fault if fault in {"denied", "policy", "partial"} else None)
    monkeypatch.setattr(diagnostic.smoke, "build_knowledge_http_client", clients)
    case = replace(diagnostic.load_dataset().cases[0], question=QUESTION,
        requirements=(KnowledgeEvidenceRequirement(requirement_id="r1", domain_id="tax.policy",
            kind=KnowledgeRequirementKind.RULE, focus=FOCUSES[0]),))
    outbound, models, key_reads = [], [], []

    def handler(request):
        outbound.append(request)
        if fault == "timeout":
            raise httpx.ReadTimeout("synthetic-secret")
        value = {"outcome": "answer", "points": [{"evidence_ref": "e1", "quote": CONTENTS[0]}],
                 "coverage": [{"requirement_id": "r1", "evidence_refs": ["e1"]}]}
        if fault == "insufficient": value = {"outcome": "insufficient_evidence", "points": [], "coverage": []}
        if fault == "coverage": value["coverage"][0]["requirement_id"] = "r2"
        if fault == "quote": value["points"][0]["quote"] = "synthetic-unquoted-secret"
        return httpx.Response(200, content=wire("{" if fault == "json" else json.dumps(value)),
                              headers={"Content-Type": "application/json"})

    def settings():
        key_reads.append(1)
        return ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-only-key"))

    def factory(*args):
        model = diagnostic.OneSummary(*args, settings_factory=settings, client_factory=lambda _: httpx.AsyncClient(
            base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False))
        models.append(model)
        return model

    originals = (RequirementCoverageValidator.validate, ExtractiveSummaryValidator.validate)
    row = await diagnostic.measure(case, "header.payload.signature", tmp_path, "a" * 64,
                                   diagnostic.smoke.LocalBudget(), model_factory=factory)
    assert row["status"] == status
    paid = int(fault not in {"denied", "policy", "partial"})
    assert len(outbound) == row["externalModelCalls"] == len(key_reads) == paid
    assert row["fixedPlanningCalls"] == 2
    assert (RequirementCoverageValidator.validate, ExtractiveSummaryValidator.validate) == originals
    if reason:
        assert [r["reason"] for r in row["validation"]["failures"]] == [reason]
        assert [r["status"] for r in row["modelTaskStates"]] == ["succeeded"] * 3
        assert row["failureCode"] == "knowledge.summary_failure"
    else:
        assert row["validation"]["failures"] == []
    assert all(c.is_closed for c in clients.clients)
    assert models[0].client is None or models[0].client.is_closed
    if paid:
        with pytest.raises(diagnostic.smoke.SmokeFailure, match="model_outbound_forbidden"):
            await models[0].outbound(outbound[0])
        assert models[0].paid == 1
    visible = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(term not in visible for term in CONTENTS + FOCUSES + (QUESTION, "header.payload.signature",
        "synthetic-only-key", "synthetic-unquoted-secret", "synthetic-secret"))


@pytest.mark.parametrize("extra", ["started.json", "consumed.json", "result.json"])
def test_no_restart_even_unconsumed_before_key_or_network(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(diagnostic, "ROOT", tmp_path)
    diagnostic.save(tmp_path / "manifest.json", {})
    diagnostic.save(tmp_path / extra, {})
    monkeypatch.setattr(diagnostic, "manifest", lambda: pytest.fail("no further preflight"))
    with pytest.raises(diagnostic.smoke.SmokeFailure, match="retry_resume_forbidden"):
        diagnostic.execute("a" * 64)


def test_changed_binding_no_started_or_service(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "ROOT", tmp_path)
    diagnostic.save(tmp_path / "manifest.json", {"version": 1})
    monkeypatch.setattr(diagnostic, "manifest", lambda: {"version": 2})
    with pytest.raises(diagnostic.smoke.SmokeFailure, match="binding_changed"):
        diagnostic.execute(diagnostic.digest((tmp_path / "manifest.json").read_bytes()))
    assert {p.name for p in tmp_path.iterdir()} == {"manifest.json"}


@pytest.mark.asyncio
async def test_forbidden_payload_no_consumption(tmp_path):
    model = diagnostic.OneSummary(diagnostic.load_dataset().cases[0], tmp_path, "a" * 64)
    model.expected = b"allowed"
    for url, payload in ((ModelSettings.BASE_URL + "/chat/completions", b"wrong"),
                          ("https://example.org/chat/completions", b"allowed")):
        with pytest.raises(diagnostic.smoke.SmokeFailure, match="model_outbound_forbidden"):
            await model.outbound(httpx.Request("POST", url, content=payload))
    assert model.paid == 0 and list(tmp_path.iterdir()) == []


def test_manifest_preparation_rejects_dirty_or_foreign_import(monkeypatch):
    monkeypatch.setattr(diagnostic, "git", lambda *args: "dirty")
    with pytest.raises(diagnostic.smoke.SmokeFailure, match="dirty_worktree"):
        diagnostic.manifest()
    monkeypatch.setattr(diagnostic, "git", lambda *args: "")
    monkeypatch.setitem(diagnostic.sys.modules, "agent_runtime.synthetic", type("Module", (), {"__file__": "C:/foreign.py"})())
    with pytest.raises(diagnostic.smoke.SmokeFailure, match="import_source_invalid"):
        diagnostic.manifest()


@pytest.mark.asyncio
async def test_cancelled_real_transport_closes_client_and_restores_validator(tmp_path, monkeypatch):
    clients = Clients()
    monkeypatch.setattr(diagnostic.smoke, "build_knowledge_http_client", clients)
    case = replace(diagnostic.load_dataset().cases[0], question=QUESTION,
        requirements=(KnowledgeEvidenceRequirement(requirement_id="r1", domain_id="tax.policy",
            kind=KnowledgeRequirementKind.RULE, focus=FOCUSES[0]),))
    models = []
    def handler(request):
        raise asyncio.CancelledError()
    def factory(*args):
        model = diagnostic.OneSummary(*args,
            settings_factory=lambda: ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic")),
            client_factory=lambda _: httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler)))
        models.append(model)
        return model
    original = ExtractiveSummaryValidator.validate
    with pytest.raises(asyncio.CancelledError):
        await diagnostic.measure(case, "header.payload.signature", tmp_path, "a" * 64,
            diagnostic.smoke.LocalBudget(), model_factory=factory)
    assert models[0].paid == 1 and models[0].client.is_closed
    assert all(c.is_closed for c in clients.clients)
    assert ExtractiveSummaryValidator.validate is original
    assert (tmp_path / "consumed.json").exists()
