"""Synthetic failures through the real gateway/decoders; never reconstruct run-09."""
from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, asdict
import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.model.contracts import InvalidModelOutput, ModelCallContext, ModelProviderFailureKind
from agent_runtime.model.deepseek.dto import parse_deepseek_response
from agent_runtime.model import gateway
from agent_runtime.model.settings import ModelSettings
from agent_runtime.observation import observation_scope
from tests.contract.knowledge.test_rewrite_task_v7 import wire_plan
from tests.integration.knowledge import test_requirement_runtime_composition as production
from tests.system_e2e import knowledge_model_failure_probe_v1 as probe
from tests.system_e2e.test_knowledge_stage_b_run_09_history import HASHES as RUN09_HASHES

SECRET = "synthetic-private-model-response-marker"


def wire(content=None, **choice_fields):
    value = {"object": "chat.completion", "model": ModelSettings.MODEL_NAME,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "content": json.dumps(wire_plan()) if content is None else content}, **choice_fields}]}
    return json.dumps(value).encode()


class Transport:
    def __init__(self, raw=None, *, error=None, wait=None):
        self.raw, self.error, self.wait = raw or wire(), error, wait
        self.calls = 0
        self.entered = asyncio.Event()

    async def complete(self, request, *, call_deadline):
        self.calls += 1
        self.entered.set()
        if self.wait is not None:
            await self.wait.wait()
        if self.error is not None:
            raise self.error
        return parse_deepseek_response(self.raw, max_bytes=65536)


async def invoke(transport):
    definition = KnowledgeRewriteTaskV8.definition()
    model = gateway.BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    with observation_scope() as collector:
        result = await model.generate(definition=definition,
            input=KnowledgeSemanticPlanInput(minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law")),
            context=ModelCallContext(request_id="test-request", correlation_id="test-correlation",
                deadline_monotonic=asyncio.get_running_loop().time() + 10))
        snapshot = collector.snapshot()
    return result, snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,code,phase,cause", [
    (b"{", "model.json_invalid", "json_boundary", "json_syntax"),
    (b"\xff", "model.json_invalid_utf8", "json_boundary", "encoding"),
    (b'{"object":1,"object":2}', "model.json_duplicate_key", "json_boundary", "unknown"),
    (b'{"object":NaN}', "model.json_non_finite_number", "json_boundary", "unknown"),
    (b"[]", "model.json_object_required", "json_boundary", "unknown"),
    (b"{}", "model.provider_response_mismatch", "provider_response", "unknown"),
    (wire(finish_reason="length"), "model.provider_finish_reason_invalid", "provider_response", "unknown"),
    (wire(index=True), "model.provider_choice_invalid", "provider_response", "unknown"),
    (wire(message={"content": 42}), "model.provider_content_invalid", "provider_response", "unknown"),
    (wire("{"), "knowledge.invalid_requirement_plan", "rewrite_decoder", "json_syntax"),
    (wire("{}"), "knowledge.invalid_requirement_plan", "rewrite_decoder", "shape_or_enum"),
    (wire(json.dumps({**wire_plan(), "question_kind": SECRET})), "knowledge.invalid_requirement_plan", "rewrite_decoder", "shape_or_enum"),
    (wire(json.dumps({**wire_plan(), "requirements": []})), "knowledge.invalid_requirement_plan", "rewrite_decoder", "semantic_contract"),
    (wire('{"outcome":1,"outcome":2}'), "knowledge.invalid_requirement_plan", "rewrite_decoder", "unknown"),
])
async def test_real_decoder_failures_have_finite_projection_and_identical_public_result(raw, code, phase, cause, caplog):
    expected, before = await invoke(Transport(raw))
    transport = Transport(raw)
    with probe.observe_failures() as collector:
        actual, after = await invoke(transport)
    assert actual == expected and actual.failure_kind is ModelProviderFailureKind.INVALID_OUTPUT
    assert after == before and transport.calls == 1
    assert collector.records == (probe.FailureDiagnostic(phase, code, cause),)
    assert not collector.overflowed
    assert SECRET not in json.dumps([asdict(row) for row in collector.records]) + caplog.text
    assert set(asdict(collector.records[0])) == {"phase", "code", "cause"}


@pytest.mark.asyncio
async def test_success_timeout_and_other_failures_remain_unmodified():
    for error in (None, TimeoutError(SECRET), RuntimeError(SECRET)):
        expected, before = await invoke(Transport(error=error))
        with probe.observe_failures() as collector:
            actual, after = await invoke(Transport(error=error))
        assert actual == expected and after == before and collector.records == ()


@pytest.mark.parametrize("code", [SECRET, "model.json_" + SECRET, None, [], 1, True])
def test_unknown_or_malformed_codes_do_not_escape_allowlist(code):
    error = InvalidModelOutput(code)
    assert probe.project_failure(error) == probe.FailureDiagnostic("unknown", "unknown", "unknown")


def test_projection_never_formats_exception_or_keeps_payload_and_bounds_cycles():
    class Untrusted(ValueError):
        def __str__(self):
            raise AssertionError("Must not format exception")
    cause = Untrusted(SECRET)
    cause.__cause__ = cause
    error = InvalidModelOutput("knowledge.invalid_requirement_plan")
    error.__cause__ = cause
    result = probe.project_failure(error)
    assert result == probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "unknown")
    assert not hasattr(result, "__dict__") and SECRET not in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.code = SECRET
    assert probe.project_failure(None).phase == "unknown"
    assert probe.project_failure(cause).code == "unknown"


def test_unknown_cause_properties_are_not_evaluated():
    class Untrusted(ValueError):
        @property
        def __cause__(self):
            raise AssertionError("Must not inspect custom cause property")
    error = InvalidModelOutput("knowledge.invalid_requirement_plan")
    error.__cause__ = Untrusted(SECRET)
    assert probe.project_failure(error).cause == "unknown"
    error.__cause__ = error
    assert probe.project_failure(error).cause == "unknown"


@pytest.mark.asyncio
async def test_cap_is_explicit_and_cannot_change_model_results():
    with probe.observe_failures() as collector:
        for _ in range(9):
            result, _ = await invoke(Transport(b"{"))
            assert result.failure_kind is ModelProviderFailureKind.INVALID_OUTPUT
    assert len(collector.records) == 8 and collector.overflowed
    snapshot = collector.records
    collector.record(InvalidModelOutput("model.json_invalid"))
    assert collector.records == snapshot


def test_nested_installation_and_failure_restore_original_callback():
    original = gateway.model_call_failed
    with pytest.raises(ValueError, match="synthetic"):
        with probe.observe_failures():
            installed = gateway.model_call_failed
            with pytest.raises(RuntimeError, match="overlapping_scope"):
                with probe.observe_failures():
                    pytest.fail("nested scope must not enter")
            assert gateway.model_call_failed is installed
            raise ValueError("synthetic")
    assert gateway.model_call_failed is original
    with probe.observe_failures() as collector:
        assert not collector.records
    assert gateway.model_call_failed is original


@pytest.mark.asyncio
async def test_other_context_is_not_captured_and_late_child_cannot_append():
    release = asyncio.Event()
    outside = Transport(b"{", wait=release)
    outside_task = asyncio.create_task(invoke(outside))  # Does not inherit the probe context.
    await outside.entered.wait()
    with probe.observe_failures() as collector:
        release.set()
        await outside_task
        assert collector.records == ()
        release.clear()
        child = Transport(b"{", wait=release)
        child_task = asyncio.create_task(invoke(child))
        await child.entered.wait()
    with probe.observe_failures() as next_collector:
        release.set()
        await child_task
    assert collector.records == next_collector.records == ()


@pytest.mark.asyncio
async def test_cancellation_propagates_and_callback_is_called_once(monkeypatch):
    original = gateway.model_call_failed
    callbacks = []
    def record(sequence, kind):
        callbacks.append(kind)
        original(sequence, kind)
    monkeypatch.setattr(gateway, "model_call_failed", record)
    with probe.observe_failures() as collector:
        await invoke(Transport(b"{"))
        waiting = Transport(wait=asyncio.Event())
        task = asyncio.create_task(invoke(waiting))
        await waiting.entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert callbacks == ["invalid_output", "cancelled"] and len(collector.records) == 1
    assert gateway.model_call_failed is record


@pytest.mark.asyncio
async def test_cancelling_scope_owner_restores_patch_and_releases_installation():
    original = gateway.model_call_failed
    waiting = Transport(wait=asyncio.Event())
    async def owner():
        with probe.observe_failures():
            await invoke(waiting)
    task = asyncio.create_task(owner())
    await waiting.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gateway.model_call_failed is original
    with probe.observe_failures() as collector:
        assert collector.records == ()


@pytest.mark.asyncio
async def test_current_runtime_stops_before_retrieval_and_preserves_observations(monkeypatch):
    value = production.plan()
    value["requirements"] = []
    with probe.observe_failures() as collector:
        result, model, clients, observation = await production.invoke(value, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert len(model.requests) == 2 and not clients.paths and all(c.is_closed for c in clients.clients)
    assert collector.records == (probe.FailureDiagnostic("rewrite_decoder", "knowledge.invalid_requirement_plan", "semantic_contract"),)
    assert observation.model_calls[-1]["failureKind"] == "invalid_output"
    assert "cause" not in observation.model_calls[-1] and "phase" not in observation.model_calls[-1]


def test_run09_original_bytes_remain_immutable_without_freezing_current_production():
    root = Path(__file__).parent / "knowledge_stage_b_run_09"
    for name, expected in RUN09_HASHES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
