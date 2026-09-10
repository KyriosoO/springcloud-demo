"""DR-KEV-032: current-root rejection observation, entirely non-live.

The scoped observer below is a test fixture, not a production hook or a live
launcher. It calls each original validator once and re-raises the same error.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
import asyncio
import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator, InvalidSummary
from tests.integration.knowledge.test_requirement_runtime_composition import CONTENTS, FOCUSES, invoke
from tests.system_e2e.knowledge_summary_failure_probe_v1 import project_summary_failure


@pytest.fixture
def observed_validators(monkeypatch):
    current = ContextVar("test_summary_observation", default=None)
    originals = {"coverage": RequirementCoverageValidator.validate, "extractive": ExtractiveSummaryValidator.validate}

    def wrapper(phase):
        original = originals[phase]

        def validate(self, **kwargs):
            record = current.get()
            if record is not None:
                record["calls"].append(phase)
            try:
                return original(self, **kwargs)
            except InvalidSummary as error:
                if record is not None:
                    # Never inspect input, output, error text or stack frames.
                    record["failures"].append(asdict(project_summary_failure(error)))
                raise

        return validate

    @contextmanager
    def request_observation():
        record = {"calls": [], "failures": []}
        token = current.set(record)
        try:
            yield record
        finally:
            current.reset(token)

    with monkeypatch.context() as patch:
        patch.setattr(RequirementCoverageValidator, "validate", wrapper("coverage"))
        patch.setattr(ExtractiveSummaryValidator, "validate", wrapper("extractive"))
        yield request_observation
    assert RequirementCoverageValidator.validate is originals["coverage"]
    assert ExtractiveSummaryValidator.validate is originals["extractive"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,reason,phases", [
    (None, None, ["coverage", "extractive"]),
    ("insufficient", None, ["coverage", "extractive"]),
    ("missing_coverage", "coverage_ids_invalid", ["coverage"]),
    ("unknown_ref", "coverage_refs_invalid", ["coverage"]),
    ("wrong_domain", "coverage_domain_mismatch", ["coverage"]),
    ("quote", "quote_not_substring", ["coverage", "extractive"]),
    ("duplicate", None, []),
    ("summary_failure", None, []),
    ("summary_timeout", None, []),
    ("rewrite_failure", None, []),
])
async def test_current_root_observes_actual_post_decode_rejection_only(
    fault, reason, phases, observed_validators, monkeypatch, caplog,
):
    with observed_validators() as record:
        result, model, clients, observation = await invoke(
            model_fault=fault, multi=fault == "wrong_domain", monkeypatch=monkeypatch,
        )
    expected = (CapabilityStatus.SUCCESS if fault is None else CapabilityStatus.NO_RESULT if fault == "insufficient"
                else CapabilityStatus.TIMEOUT if fault == "summary_timeout" else CapabilityStatus.DOWNSTREAM_FAILURE)
    assert result.status is expected
    assert record["calls"] == phases  # No validator re-entry or second attempt.
    assert len(model.requests) == (2 if fault == "rewrite_failure" else 3)
    if reason is not None:
        assert [row["reason"] for row in record["failures"]] == [reason]
        assert [(task["taskId"], task["status"]) for task in observation.model_calls] == [
            ("action_selection", "succeeded"), ("knowledge_rewrite", "succeeded"), ("knowledge_summary", "succeeded"),
        ]
        assert result.user_result is None and result.failure.code == "knowledge.summary_failure"
    else:
        assert record["failures"] == []
    if fault == "insufficient":
        assert result.user_result["reason"] == "insufficient_evidence"
    if fault == "rewrite_failure":
        assert clients.paths == []
    else:
        assert clients.paths.count("/es/knowledge/search") == (4 if fault == "wrong_domain" else 2)
        assert clients.paths.count("/rerank") == 3
    visible = json.dumps(record, ensure_ascii=False) + json.dumps(asdict(observation), ensure_ascii=False) + caplog.text
    assert all(value not in visible for value in CONTENTS + FOCUSES + ("header.payload.signature",))
    assert all(client.is_closed for client in clients.clients)


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_mix_rejections_or_retain_observation(observed_validators):
    async def call(fault):
        with observed_validators() as record:
            result, _, _, _ = await invoke(model_fault=fault)
        return result, record

    runs = await asyncio.gather(call("quote"), call("missing_coverage"), call(None))
    assert [result.status for result, _ in runs] == [CapabilityStatus.DOWNSTREAM_FAILURE,
        CapabilityStatus.DOWNSTREAM_FAILURE, CapabilityStatus.SUCCESS]
    assert [[r["reason"] for r in record["failures"]] for _, record in runs] == [
        ["quote_not_substring"], ["coverage_ids_invalid"], [],
    ]
    assert [record["calls"] for _, record in runs] == [
        ["coverage", "extractive"], ["coverage"], ["coverage", "extractive"],
    ]
    frozen = json.dumps([record for _, record in runs], sort_keys=True)
    # Wrappers remain installed here, but the ended request scope must not leak.
    result, _, _, _ = await invoke(model_fault="quote")
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert json.dumps([record for _, record in runs], sort_keys=True) == frozen


@pytest.mark.asyncio
async def test_cancellation_restores_observation_scope_without_manufacturing_failure(observed_validators, monkeypatch):
    from agent_runtime.model.contracts import ModelTaskId
    from tests.integration.knowledge.test_requirement_runtime_composition import Model

    entered, instances, records = asyncio.Event(), [], []
    original = Model.complete

    async def observed_model(self, request, *, call_deadline):
        if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            instances.append(self)
            entered.set()
        return await original(self, request, call_deadline=call_deadline)

    async def waiting_request():
        with observed_validators() as record:
            records.append(record)
            await invoke(model_fault="wait")

    with monkeypatch.context() as patch:
        patch.setattr(Model, "complete", observed_model)
        task = asyncio.create_task(waiting_request())
        try:
            await asyncio.wait_for(entered.wait(), 2)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert len(instances) == 1 and instances[0].released.is_set()
    assert len(instances[0].requests) == 3
    assert records == [{"calls": [], "failures": []}]
    result, _, _, _ = await invoke(model_fault="quote")
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert records == [{"calls": [], "failures": []}]
