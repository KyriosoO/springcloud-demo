"""V3 observes shape rejections without admitting, repairing, or replaying them."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge import rewrite_v7
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse
from tests.integration.knowledge import test_rewrite_v9_period_lookup_diagnosis as boundary
from tests.integration.knowledge.test_requirement_runtime_composition import invoke
from tests.system_e2e import knowledge_model_failure_probe_v1 as legacy
from tests.system_e2e import knowledge_model_failure_probe_v2 as semantic
from tests.system_e2e import knowledge_model_failure_probe_v3 as probe
from tests.system_e2e.test_knowledge_model_failure_probe_v2 import EXPECTED


def response(value):
    return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content=json.dumps(value),
        tool_calls=(), usage_total_tokens=0)


def parse(value):
    return KnowledgeRewriteTaskV9.definition().parse_response(response(value))


SHAPES = [
    pytest.param((), [], "root_shape", id="root-array"),
    pytest.param(("extra",), "synthetic-secret", "root_fields", id="unknown-root-key"),
    pytest.param(("question_kind",), None, "question_kind_type", id="null-kind"),
    pytest.param(("queries",), {}, "collection_type", id="queries-object"),
    pytest.param(("queries",), [{}] * 3, "collection_limit", id="query-limit"),
    pytest.param(("requirements",), [{}] * 5, "collection_limit", id="requirement-limit"),
    pytest.param(("missing_conditions",), [None] * 4, "collection_limit", id="missing-limit"),
    pytest.param(("queries", 0), [], "query_shape", id="query-array"),
    pytest.param(("queries", 0), {"domain_id": "tax.policy"}, "query_shape", id="query-key-missing"),
    pytest.param(("requirements", 0), [], "requirement_shape", id="requirement-array"),
    pytest.param(("requirements", 0, "kind"), 1, "requirement_shape", id="requirement-kind-number"),
    pytest.param(("requirements", 0, "kind"), "synthetic-secret", "requirement_kind_enum", id="requirement-enum"),
    pytest.param(("question_kind",), "synthetic-secret", "question_kind_enum", id="question-enum"),
]


def changed(path, replacement):
    if not path:
        return replacement
    value = deepcopy(boundary.declared_plan())
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    return value


@pytest.mark.parametrize("path,replacement,detail", SHAPES)
def test_original_rejection_and_finite_classification(path, replacement, detail):
    value = changed(path, replacement)
    with pytest.raises(InvalidModelOutput) as before:
        parse(value)
    with probe.observe_failures() as collector:
        with pytest.raises(InvalidModelOutput) as after:
            parse(value)
        assert type(after.value) is type(before.value)
        assert after.value.code == before.value.code == "knowledge.invalid_requirement_plan"
        assert type(after.value.__cause__) is type(before.value.__cause__) is ValueError
        projected = probe.project_failure(after.value)
        assert projected.detail == detail and projected.cause == "shape_or_enum"
        assert "synthetic-secret" not in repr(projected)
        assert probe._REJECTED.get() is None and probe._FACT.get() == "unknown"
        assert not collector.records
        assert probe.project_failure(after.value).detail == "unknown"


@pytest.mark.parametrize("variant,detail", zip(boundary.INVALID_VALUES, EXPECTED, strict=True),
    ids=[item.id for item in boundary.INVALID_VALUES])
def test_semantic_details_are_preserved(variant, detail):
    path, replacement, _ = variant.values
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput) as error:
            parse(boundary.changed_plan(path, replacement))
        assert probe.project_failure(error.value).detail == detail


@pytest.mark.parametrize("outcome", ["search", "unsupported", "clarification_required"])
def test_accepted_terminal_results_and_original_hooks_unchanged(monkeypatch, outcome):
    value = boundary.declared_plan() if outcome == "search" else dict(outcome=outcome,
        question_kind="none", queries=[], requirements=[], missing_conditions=["subject"] if outcome == "clarification_required" else [])
    expected = parse(value)
    load = json.loads
    calls = []
    class Counted:
        @staticmethod
        def loads(*args, **kwargs):
            calls.append(kwargs)
            return load(*args, **kwargs)
    monkeypatch.setattr(probe, "_JSON", Counted)
    with probe.observe_failures() as collector:
        assert parse(value) == expected
        assert not collector.records and probe._REJECTED.get() is None
    assert calls == [dict(object_pairs_hook=rewrite_v7._unique, parse_constant=rewrite_v7._constant)]
    assert json.loads is load


def test_json_proxy_returns_exact_original_tree_and_parse_returns_exact_output(monkeypatch):
    value = boundary.declared_plan()
    expected = parse(value)
    class Fixed:
        @staticmethod
        def loads(*args, **kwargs): return value
    monkeypatch.setattr(probe, "_JSON", Fixed)
    with probe.observe_failures():
        assert rewrite_v7.json.loads("not actually parsed") is value
        monkeypatch.setattr(probe, "_PARSE", lambda _: expected)
        assert parse(value) is expected


@pytest.mark.parametrize("text,cause", [("{", "json_syntax"), ('{"x":1,"x":2}', "unknown"),
    ('{"x":NaN}', "unknown"), ('{"x":Infinity}', "unknown"), ('{} {}', "json_syntax")])
def test_json_boundary_not_misclassified_as_shape(text, cause):
    item = response({})
    from dataclasses import replace
    item = replace(item, content=text)
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput) as error:
            KnowledgeRewriteTaskV9.definition().parse_response(item)
        fact = probe.project_failure(error.value)
        assert fact.cause == cause and fact.detail == "unknown"


def test_json_engine_value_error_does_not_reuse_previous_fact(monkeypatch):
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput): parse([])
        class Broken:
            @staticmethod
            def loads(*args, **kwargs): raise ValueError("synthetic-private-engine-error")
        monkeypatch.setattr(probe, "_JSON", Broken)
        with pytest.raises(InvalidModelOutput) as caught: parse({})
        fact = probe.project_failure(caught.value)
        assert fact.cause == "shape_or_enum" and fact.detail == "unknown"
        assert "synthetic-private" not in repr(fact)


@pytest.mark.parametrize("broken", ["raise", "untrusted"])
def test_projection_fault_does_not_change_original_failure(monkeypatch, broken):
    original = InvalidModelOutput("knowledge.invalid_requirement_plan")
    def fail_projection(value):
        if broken == "raise": raise RuntimeError("synthetic-private")
        return "synthetic-private"
    def fail_parse(item):
        rewrite_v7.json.loads(item.content)
        raise original
    monkeypatch.setattr(probe, "shape_detail", fail_projection)
    monkeypatch.setattr(probe, "_PARSE", fail_parse)
    with probe.observe_failures():
        with pytest.raises(InvalidModelOutput) as caught: parse([])
        assert caught.value is original
        assert probe.project_failure(caught.value).detail == "unknown"


def test_unobserved_thread_and_prebuilt_task_do_not_inspect_tree(monkeypatch):
    old = KnowledgeRewriteTaskV9.definition()
    with probe.observe_failures():
        monkeypatch.setattr(probe, "shape_detail", lambda _: pytest.fail("not in a parse observation"))
        with pytest.raises(InvalidModelOutput): old.parse_response(response([]))
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(InvalidModelOutput): pool.submit(parse, []).result(timeout=3)
        assert probe._REJECTED.get() is None


@pytest.mark.asyncio
async def test_async_context_isolation_mismatch_and_late_child():
    barrier = asyncio.Event()
    async def one(value):
        try: parse(value)
        except InvalidModelOutput as error:
            await barrier.wait()
            return probe.project_failure(error).detail
    with probe.observe_failures():
        first = asyncio.create_task(one([]))
        second = asyncio.create_task(one(changed(("question_kind",), "invalid")))
        await asyncio.sleep(0)
        barrier.set()
        assert await asyncio.gather(first, second) == ["root_shape", "question_kind_enum"]
        assert probe._REJECTED.get() is None
        with pytest.raises(InvalidModelOutput): parse([])
        assert probe.project_failure(InvalidModelOutput("knowledge.invalid_requirement_plan")).detail == "unknown"
        barrier.clear()
        late = asyncio.create_task(one([]))
        await asyncio.sleep(0)
    barrier.set()
    assert await late == "unknown"


def test_cancel_uninstalls_and_preserves_source_bytes():
    hooks = (rewrite_v7.json, rewrite_v7._parse, legacy.project_failure)
    sources = {Path(m.__file__): Path(m.__file__).read_bytes() for m in (rewrite_v7, legacy, semantic)}
    with pytest.raises(asyncio.CancelledError), probe.observe_failures():
        with pytest.raises(RuntimeError, match="overlapping_scope"), probe.observe_failures(): pass
        with pytest.raises(InvalidModelOutput): parse([])
        raise asyncio.CancelledError()
    assert (rewrite_v7.json, rewrite_v7._parse, legacy.project_failure) == hooks
    assert probe._SCOPE.get() is None and probe._REJECTED.get() is None and not probe._PARSING.get()
    assert all(path.read_bytes() == content for path, content in sources.items())


def test_custom_type_never_runs_attributes():
    class Hostile:
        def __getattribute__(self, key): raise AssertionError("custom object inspected")
    assert probe.shape_detail(Hostile()) == "unknown"


def test_projection_is_nonmutating_and_does_not_traverse_over_limit_items():
    class Hostile:
        def __getattribute__(self, key): raise AssertionError("oversized contents inspected")
    value = boundary.declared_plan()
    saved = deepcopy(value)
    assert probe.shape_detail(value) == "unknown" and value == saved
    value["queries"] = [Hostile()] * 3
    assert probe.shape_detail(value) == "collection_limit"


def test_success_clears_nested_failure_identity(monkeypatch):
    expected = parse(boundary.declared_plan())
    original = probe._PARSE
    def nested(item):
        monkeypatch.setattr(probe, "_PARSE", original)
        with pytest.raises(InvalidModelOutput): parse([])
        return expected
    with probe.observe_failures():
        monkeypatch.setattr(probe, "_PARSE", nested)
        assert parse(boundary.declared_plan()) is expected
        assert probe._REJECTED.get() is None and probe._FACT.get() == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,replacement,detail", SHAPES[1:])
async def test_current_production_root_rejects_with_zero_downstream(path, replacement, detail, monkeypatch):
    value = changed(path, replacement)
    before, _, old_clients, _ = await invoke(value, question=boundary.QUESTION, monkeypatch=monkeypatch)
    with probe.observe_failures() as collector:
        actual, model, clients, observation = await invoke(value, question=boundary.QUESTION, monkeypatch=monkeypatch)
    assert actual.status is before.status and actual.failure == before.failure
    assert clients.paths == old_clients.paths == [] and len(model.requests) == 2
    assert observation.plans == () and len(collector.records) == 1
    record = asdict(collector.records[0])
    assert record["detail"] == detail and record["cause"] == "shape_or_enum"
    assert all(text not in repr(record) for text in boundary.FOCUSES + (boundary.QUESTION, "synthetic-secret"))
