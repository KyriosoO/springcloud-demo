"""DR-KEV-032: current-root rejection observation, entirely non-live.

The scoped observer below is a test fixture, not a production hook or a live
launcher. It calls each original validator once and re-raises the same error.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
import asyncio
import json
import time

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
@pytest.mark.parametrize("startup_delay", [0.0, 2.05], ids=["normal-startup", "slow-startup"])
async def test_cancellation_restores_observation_scope_without_manufacturing_failure(observed_validators, monkeypatch, startup_delay):
    from agent_runtime.model.contracts import ModelTaskId
    from tests.integration.knowledge import test_requirement_runtime_composition as harness

    async def forbidden_business(*args, **kwargs):
        pytest.fail("Knowledge cancellation must not invoke Business")

    original_build = harness.build_runtime

    def delayed_build(*args, **kwargs):
        # 慢启动反例：即使构建超过等待上限，也不应提前取消尚未开始的请求。
        time.sleep(startup_delay)
        return original_build(*args, **kwargs)

    monkeypatch.setattr(harness, "build_runtime", delayed_build)
    monkeypatch.setattr(harness.HttpxBusinessDomainTransport, "send", forbidden_business)
    model, clients = harness.Model(harness.plan(), fault="wait"), harness.Clients()
    # 取消验证针对已启动Runtime内的请求，不把同步配置/HTTP client构建计入2秒等待。
    runtime = harness.build_runtime(
        {**harness._enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
        model_transport=model, knowledge_http_client_factory=clients,
    )
    records = []

    async def waiting_request():
        with observed_validators() as record, harness.observation_scope():
            records.append(record)
            await runtime.ainvoke(question=harness.QUESTION, scope=harness.scope(harness.QUESTION))

    task = asyncio.create_task(waiting_request())
    try:
        await asyncio.wait_for(model.entered.wait(), 2)
    finally:
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await runtime.aclose()
            await runtime.aclose()
    assert model.released.is_set() and all(client.is_closed for client in clients.clients)
    assert [request.task_id for request in model.requests] == [
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY,
    ]
    assert records == [{"calls": [], "failures": []}]
    result, _, _, _ = await invoke(model_fault="quote")
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert records == [{"calls": [], "failures": []}]
