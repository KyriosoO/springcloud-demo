"""Current-root compatibility proof; no frozen runner changes or new live entrypoint."""
import asyncio
from dataclasses import asdict
import json

import pytest

from agent_runtime.model import gateway
from tests.contract.knowledge import test_rewrite_v9_failure_boundary as boundary
from tests.integration.knowledge import test_requirement_runtime_composition as production
from tests.system_e2e import knowledge_model_failure_probe_v1 as probe
from tests.system_e2e import knowledge_representative_uat_v2 as runner
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    (None, ()),
    ("envelope", (probe.FailureDiagnostic("provider_response", "model.provider_response_mismatch", "unknown"),)),
    ("truncated", (probe.FailureDiagnostic("provider_response", "model.provider_finish_reason_invalid", "unknown"),)),
    ("json", (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "json_syntax"),)),
    ("extra_field", (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "shape_or_enum"),)),
    ("missing_requirements", (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "shape_or_enum"),)),
    # The historical allowlist does not cover response headers. Do not invent detail.
    ("content_type", (probe.FailureDiagnostic("unknown", "unknown", "unknown"),)),
])
async def test_existing_probe_classifies_current_http_and_rewrite_boundaries(fault, expected):
    original = gateway.model_call_failed
    with probe.observe_failures() as collector:
        # Real transport/Gateway/Rewrite9, but only MockTransport and a synthetic key.
        await boundary.test_distinct_response_errors_share_invalid_output_without_retry(fault)
    assert collector.records == expected
    assert not collector.overflowed
    assert gateway.model_call_failed is original


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    (None, ()),
    ("invalid_plan", (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "semantic_contract"),)),
    ("invalid_output", (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "json_syntax"),)),
    ("timeout", ()),
])
async def test_observer_preserves_current_root_result_counts_and_safe_evidence(tmp_path, monkeypatch, caplog, fault, expected):
    monkeypatch.setattr(shared, "runner", runner)
    public_records = []
    original_assess = runner.assess

    def assess(case, response, observation, budget):
        # Exclude timing-dependent downstream spans, but compare actual public output
        # and model/plan observations, not only the derived pass/fail verdict.
        public_records.append((response, observation.model_calls, observation.plans))
        return original_assess(case, response, observation, budget)

    monkeypatch.setattr(runner, "assess", assess)
    before_path, after_path = tmp_path / "without-observer", tmp_path / "with-observer"
    before_path.mkdir()
    after_path.mkdir()
    before = await shared.invoke(before_path, monkeypatch, fault)
    original = gateway.model_call_failed
    with probe.observe_failures() as collector:
        after = await shared.invoke(after_path, monkeypatch, fault)
    assert after == before  # Public verdict, every downstream count, model HTTP count.
    assert len(public_records) == 2 and public_records[0] == public_records[1]
    row, counts, requests = after
    assert requests == counts["model"] == (3 if fault is None else 2)
    assert row["passed"] is (fault is None)
    if fault is not None:
        assert counts["search"] == counts["embedding"] == counts["rerank"] == 0
    assert collector.records == expected and not collector.overflowed
    assert gateway.model_call_failed is original
    diagnostics = [asdict(item) for item in collector.records]
    assert all(set(item) == {"phase", "code", "cause"} for item in diagnostics)
    visible = json.dumps([row, diagnostics], ensure_ascii=False) + caplog.text
    visible += "".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*") if path.is_file())
    forbidden = production.CONTENTS + production.FOCUSES + (
        shared.KEY, production.QUESTION, "synthetic-private-error", "header.payload.signature",
    )
    assert all(value not in visible for value in forbidden)


@pytest.mark.asyncio
async def test_current_runner_cancellation_restores_observer_and_closes_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "runner", runner)
    original = gateway.model_call_failed
    with pytest.raises(asyncio.CancelledError):
        with probe.observe_failures() as collector:
            # The shared fixture also asserts closure of every model/domain client.
            await shared.invoke(tmp_path, monkeypatch, "cancel")
    assert collector.records == ()
    assert gateway.model_call_failed is original
    assert len((tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    with probe.observe_failures() as next_collector:
        assert next_collector.records == ()
