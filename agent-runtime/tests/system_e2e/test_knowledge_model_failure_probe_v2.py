"""Finite diagnosis never changes the real decoder or public result."""
import asyncio
from dataclasses import asdict
from pathlib import Path

import pytest

from agent_runtime.knowledge import rewrite_v7
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.model.contracts import InvalidModelOutput
from tests.integration.knowledge import test_rewrite_v9_period_lookup_diagnosis as boundary
from tests.integration.knowledge.test_requirement_runtime_composition import invoke
from tests.system_e2e import knowledge_model_failure_probe_v1 as legacy
from tests.system_e2e import knowledge_model_failure_probe_v2 as probe


EXPECTED = (
    "query_count", "query_text", "query_text", "query_text", "query_text", "query_text",
    "search_missing_conditions", "missing_conditions", "terminal_state", "requirement_count",
    "requirement_id", "requirement_domain", "focus_text", "focus_text", "focus_text", "focus_text",
    "applicability_roles", "domains", "domain_coverage",
)


@pytest.mark.parametrize("variant,detail", zip(boundary.INVALID_VALUES, EXPECTED, strict=True),
                         ids=[item.id for item in boundary.INVALID_VALUES])
def test_rejected_structure_is_finite_and_original_cause_is_preserved(variant, detail):
    path, replacement, code = variant.values
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput) as caught:
            boundary.parse(boundary.changed_plan(path, replacement))
        original_error = caught.value
        assert type(original_error.__cause__) is KnowledgeInputError
        assert original_error.__cause__.code == code
        assert asdict(probe.project_failure(original_error)) == {**boundary.DIAGNOSTIC, "detail": detail}
        assert probe._REJECTED.get() is None
        assert probe.project_failure(original_error).detail == "unknown"
    assert probe._REJECTED.get() is None


def test_unknown_types_never_execute_attributes_or_serialize_content():
    class Hostile:
        def __getattribute__(self, name):
            raise AssertionError("must not inspect custom object")
    assert probe.rejected_detail(Hostile()) == "unknown"
    assert probe.project_failure(Hostile()).detail == "unknown"


def test_observer_failure_reraises_the_same_original_exception(monkeypatch):
    original = KnowledgeInputError("knowledge.invalid_requirement_plan")
    def reject(*args, **kwargs):
        raise original
    def broken(*args):
        raise RuntimeError("synthetic private text")
    monkeypatch.setattr(probe, "_VALIDATE", reject)
    monkeypatch.setattr(probe, "rejected_detail", broken)
    with probe.observe_failures():
        with pytest.raises(KnowledgeInputError) as caught:
            rewrite_v7.validate_requirement_plan_output(boundary.parse.__name__, enabled_domain_ids=())
        assert caught.value is original
    assert probe._REJECTED.get() is None


@pytest.mark.parametrize("outcome", ["search", "unsupported", "clarification_required"])
def test_valid_terminal_results_do_not_invoke_diagnosis(monkeypatch, outcome):
    value = boundary.declared_plan() if outcome == "search" else dict(
        outcome=outcome, question_kind="none", queries=[], requirements=[],
        missing_conditions=["subject"] if outcome == "clarification_required" else [],
    )
    expected = boundary.parse(value)
    monkeypatch.setattr(probe, "rejected_detail", lambda *args: pytest.fail("must not diagnose a valid plan"))
    with probe.observe_failures() as collector:
        assert boundary.parse(value) == expected
        assert not collector.records and probe._REJECTED.get() is None


@pytest.mark.asyncio
async def test_interleaved_contexts_never_reuse_another_rejection():
    barrier = asyncio.Event()
    async def one(path, replacement):
        try:
            boundary.parse(boundary.changed_plan(path, replacement))
        except InvalidModelOutput as error:
            await barrier.wait()
            return probe.project_failure(error).detail
    with probe.observe_failures():
        first = asyncio.create_task(one(("queries",), []))
        second = asyncio.create_task(one(("requirements",), []))
        await asyncio.sleep(0)
        barrier.set()
        assert await asyncio.gather(first, second) == ["query_count", "requirement_count"]
        assert probe._REJECTED.get() is None


def test_mismatched_exception_and_cancellation_release_context_and_restore_hooks():
    hooks = (legacy.project_failure, rewrite_v7.validate_requirement_plan_output)
    old_bytes = Path(legacy.__file__).read_bytes()
    with pytest.raises(asyncio.CancelledError), probe.observe_failures():
        with pytest.raises(InvalidModelOutput):
            boundary.parse(boundary.changed_plan(("requirements",), []))
        assert probe.project_failure(InvalidModelOutput("knowledge.invalid_requirement_plan")).detail == "unknown"
        with pytest.raises(RuntimeError, match="overlapping_scope"), probe.observe_failures():
            pass
        assert legacy.project_failure is probe.project_failure
        raise asyncio.CancelledError()
    assert (legacy.project_failure, rewrite_v7.validate_requirement_plan_output) == hooks
    assert probe._REJECTED.get() is None and Path(legacy.__file__).read_bytes() == old_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("path,replacement,detail", [
    (("requirements",), [], "requirement_count"),
    (("question_kind",), "applicability", "applicability_roles"),
    (("queries", 0, "query"), "", "query_text"),
])
async def test_current_root_outcome_and_calls_are_unchanged(path, replacement, detail, monkeypatch):
    value = boundary.changed_plan(path, replacement)
    without, _, clients_before, obs_before = await invoke(value, question=boundary.QUESTION, monkeypatch=monkeypatch)
    with probe.observe_failures() as collector:
        actual, model, clients_after, obs_after = await invoke(value, question=boundary.QUESTION, monkeypatch=monkeypatch)
    assert actual.status is without.status and actual.failure == without.failure
    assert clients_before.paths == clients_after.paths == [] and len(model.requests) == 2
    assert obs_before.plans == obs_after.plans == ()
    assert [asdict(record) for record in collector.records] == [{**boundary.DIAGNOSTIC, "detail": detail}]
    assert all(focus not in repr(collector.records) for focus in boundary.FOCUSES)
