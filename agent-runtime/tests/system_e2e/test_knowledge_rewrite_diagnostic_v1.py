"""Offline readiness for the single-call diagnostic; real network never used."""
import asyncio
import hashlib
import json

import httpx
import pytest

from agent_runtime.model import gateway
from agent_runtime.model.contracts import InvalidModelOutput
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.system_e2e import knowledge_rewrite_diagnostic_v1 as diagnostic
from tests.system_e2e.test_knowledge_model_failure_probe_v1 import wire
from tests.system_e2e.test_knowledge_stage_b_run_09_history import valid_lookup, HASHES


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,site", [
    ("valid", None), ("root", "root_fields"), ("types", "field_types"),
    ("limits", "list_limits"), ("query", "query_fields"),
    ("requirement", "requirement_fields"), ("kind", "requirement_kind"),
    ("question_kind", "question_kind"), ("id", "requirement_item"),
    ("coverage", "domain_coverage"), ("roles", "applicability_roles"),
    ("json", "task_json"), ("duplicate", "duplicate_key"),
])
async def test_exact_branch_and_no_payloads_or_extra_calls(tmp_path, fault, site):
    plan = valid_lookup()
    if fault == "root": del plan["queries"]
    elif fault == "types": plan["queries"] = {}
    elif fault == "limits": plan["queries"] *= 3
    elif fault == "query": plan["queries"][0]["extra"] = True
    elif fault == "requirement": plan["requirements"][0]["extra"] = True
    elif fault == "kind": plan["requirements"][0]["kind"] = "synthetic-private-marker"
    elif fault == "question_kind": plan["question_kind"] = "synthetic-private-marker"
    elif fault == "id": plan["requirements"][0]["requirement_id"] = "r2"
    elif fault == "coverage":
        plan["queries"].append(dict(domain_id="tax.law", query="增值税法律"))
    elif fault == "roles": plan["question_kind"] = "applicability"
    content = "{" if fault == "json" else '{"a":1,"a":2}' if fault == "duplicate" else json.dumps(plan)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=wire(content), headers={"Content-Type": "application/json"})
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-only-key"))
    client = httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler))
    before = gateway.model_call_failed
    result = await diagnostic.measure(client, settings, tmp_path, "a" * 64)
    assert result["status"] == "measured" and result["counts"] == {**{k: 0 for k in diagnostic.LIMITS}, "model": 1}
    assert client.is_closed and gateway.model_call_failed is before and len(calls) == 1
    if site is None:
        assert result["failureKind"] is None and result["diagnostics"] == [] and result["outputSummary"]["outcome"] == "search"
    else:
        assert result["failureKind"] == "invalid_output" and result["outputSummary"] is None
        assert result["diagnostics"][0]["throwSite"] == site
    for path in tmp_path.iterdir():
        raw = path.read_text()
        assert all(term not in raw for term in ("synthetic-private-marker", "synthetic-only-key", diagnostic.CASES[1]["question"], "focus", "quote"))
    with pytest.raises(FileExistsError):
        diagnostic.save(tmp_path / "result.json", {})


@pytest.mark.asyncio
async def test_consumed_directory_rejected_before_key_read(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "ROOT", tmp_path)
    diagnostic.save(tmp_path / "consumed.json", {})
    class NoRead(dict):
        def get(self, key, default=None):
            if key == "LLM_API_KEY": raise AssertionError("Key must not be read")
            return super().get(key, default)
    with monkeypatch.context() as scoped:
        scoped.setattr(diagnostic.os, "environ", NoRead())
        with pytest.raises(ValueError, match="retry_resume_forbidden"):
            await diagnostic.execute("a" * 64)


@pytest.mark.asyncio
async def test_second_request_is_rejected_and_client_closes(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=wire(), headers={"Content-Type": "application/json"})
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-key"))
    client = httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler))
    await diagnostic.measure(client, settings, tmp_path, "a" * 64)
    with pytest.raises(ValueError, match="outbound_forbidden"):
        await client.event_hooks["request"][0](calls[0])
    assert len(calls) == 1 and client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [httpx.ReadTimeout("synthetic-secret"), asyncio.CancelledError()])
async def test_error_is_finite_with_cleanup_and_no_retry(tmp_path, error):
    def handler(request): raise error
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-key"))
    client = httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler))
    result = await diagnostic.measure(client, settings, tmp_path, "a" * 64)
    assert client.is_closed and result["counts"]["model"] == 1
    assert "synthetic-secret" not in json.dumps(result)


def test_unknown_exception_not_inspected_and_old_hashes_preserved():
    class Unknown(ValueError):
        @property
        def __traceback__(self): raise AssertionError("unknown frames forbidden")
    assert diagnostic.throw_site(Unknown("secret")) == "unknown"
    error = InvalidModelOutput("model.json_invalid")
    error.__cause__ = error
    assert diagnostic.throw_site(error) == "unknown"
    root = diagnostic.REPO / "agent-runtime/tests/system_e2e/knowledge_stage_b_run_09"
    assert {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in HASHES} == HASHES


@pytest.mark.asyncio
async def test_changed_binding_rejected_before_client(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "ROOT", tmp_path)
    diagnostic.save(tmp_path / "manifest.json", {"version": 1})
    monkeypatch.setattr(diagnostic, "manifest", lambda: {"version": 2})
    monkeypatch.setattr(diagnostic, "build_deepseek_http_client", lambda *_: pytest.fail("no client"))
    for sha in ("0" * 64, diagnostic.digest((tmp_path / "manifest.json").read_bytes())):
        with pytest.raises(ValueError, match="binding_changed"):
            await diagnostic.execute(sha)


def test_import_source_and_dirty_worktree_fail_closed(monkeypatch):
    monkeypatch.setattr(diagnostic, "git", lambda *args: "dirty")
    with pytest.raises(ValueError, match="dirty_worktree"):
        diagnostic.manifest()
    monkeypatch.setattr(diagnostic, "git", lambda *args: "")
    monkeypatch.setitem(diagnostic.sys.modules, "agent_runtime.unknown_test_module", type("Module", (), {"__file__": "C:/untrusted/package.py"})())
    with pytest.raises(ValueError, match="import_source_invalid"):
        diagnostic.manifest()
