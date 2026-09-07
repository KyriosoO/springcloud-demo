"""Synthetic counterexamples: matching words are not matching cited sources."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput, SummaryCoverageInput, SummaryEvidenceInput,
)
from tests.system_e2e.knowledge_stage_b_citation_check import check_citations
from tests.unit.knowledge.evidence.test_summary_validation_reasons import _bundle


def fixture():
    base = _bundle()
    sources = tuple(replace(base.evidence[0], evidence_id=f"synthetic-{i}", rank=i,
        chunk_id=f"c{i}", document_id=f"d{i}", content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest())
        for i, content in enumerate(("规则甲的正文。共同语句。", "规则乙的正文。共同语句。"), 1))
    bundle = replace(base, evidence=sources)
    model = KnowledgeSummaryInput(schema_version=1, question=bundle.question_trace.minimized_question,
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=tuple(SummaryEvidenceInput(evidence_ref=f"e{i}", content=e.content, domain_ids=e.domain_ids)
                       for i, e in enumerate(sources, 1)))
    gold = {"rule": {"chunk": "c1", "sha256": sources[0].content_sha256, "clause": "共同语句。"}}
    return bundle, model, gold


def point(index=1, quote="共同语句。"):
    return {"quote": quote, "citation": {"evidenceId": f"synthetic-{index}", "domainIds": ["tax.policy"]}}


def evaluate(points=None, *, bundle=None, model=None, gold=None):
    b, m, g = fixture()
    return check_citations(bundle=b if bundle is None else bundle, summary_input=m if model is None else model,
                           required=g if gold is None else gold, points=[point()] if points is None else points)


def test_frozen_assessor_counterexample_is_not_a_reclassification_of_a_live_run():
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads(Path(__file__).with_name("knowledge_stage_b_run_07").joinpath("manifest.json").read_bytes())
    path = "agent-runtime/tests/system_e2e/knowledge_stage_b_cases.py"
    frozen = subprocess.check_output(["git", "show", f"{manifest['frozenHead']}:{path}"], cwd=root)
    assert hashlib.sha256(frozen).hexdigest() == manifest["assets"][path]
    namespace = {"__name__": "frozen_citation_counterexample"}
    exec(compile(frozen, path, "exec"), namespace)
    bundle, model, gold = fixture()
    namespace["GOLD"] = gold  # Synthetic in-memory data, never the frozen file or original gold.
    spec = {"requiredGold": ["rule"], "reason": None, "domains": ["tax.policy"]}
    observed = SimpleNamespace(plans=[{"type": "knowledge_retrieval_plan", "plan": {
        "selected_domain_ids": ["tax.policy"]}}])
    response = {"capabilityId": "knowledge.query", "status": "success", "result": {"points": [point(2)]}}
    inputs = [{"sha256": e.content_sha256, "content": e.content} for e in bundle.evidence]
    assert namespace["assess"](spec, response, observed, inputs)["passed"] is True
    checked = check_citations(bundle=bundle, summary_input=model, points=response["result"]["points"], required=gold)
    assert checked.binding_valid and checked.required_clauses == (("rule", False),)
    assert checked.failure_reason == "required_source_not_cited"


def test_actual_cited_gold_source_passes_and_emits_only_a_finite_verdict():
    verdict = evaluate()
    assert asdict(verdict) == {"binding_valid": True, "required_clauses": (("rule", True),), "failure_reason": None}
    assert not any(text in json.dumps(asdict(verdict), ensure_ascii=False)
                   for text in ("共同语句", "规则甲", "synthetic-1"))


@pytest.mark.parametrize("points", [[], None, {}, [None], [point(), point()],
    [point(3)], [point(1, "规则乙的正文。")], [point(1, "")], [point(1, "共同\n语句。")],
    [point(1, "x" * 513)], [{"quote": "共同语句。", "citation": None}],
    [{"quote": "共同语句。", "citation": {"evidenceId": [], "domainIds": ["tax.policy"]}}],
    [{"quote": "共同语句。", "citation": {"evidenceId": "synthetic-1", "domainIds": ["tax.law"]}}],
])
def test_malformed_unknown_duplicate_or_mismatched_citation_fails_closed(points):
    bundle, model, gold = fixture()
    result = check_citations(bundle=bundle, summary_input=model, points=points, required=gold)
    assert result.binding_valid is False and result.required_clauses == (("rule", False),)
    assert result.failure_reason == "citation_invalid"


@pytest.mark.parametrize("change", ["question", "content", "ref", "missing", "duplicate", "domain", "coverage", "schema",
                                    "boolean_schema", "integer_coverage", "integer_domain_coverage"])
def test_request_local_actual_model_input_must_match_the_verified_bundle(change):
    bundle, model, gold = fixture()
    if change == "question":
        model = replace(model, question="另一个请求")
    elif change == "content":
        model = replace(model, evidence=(replace(model.evidence[0], content="不同正文"), model.evidence[1]))
    elif change == "ref":
        model = replace(model, evidence=(replace(model.evidence[0], evidence_ref="e3"), model.evidence[1]))
    elif change == "missing":
        model = replace(model, evidence=model.evidence[:1])
    elif change == "duplicate":
        model = replace(model, evidence=(model.evidence[0], model.evidence[0]))
    elif change == "domain":
        model = replace(model, evidence=(replace(model.evidence[0], domain_ids=("tax.law",)), model.evidence[1]))
    elif change == "coverage":
        model = replace(model, coverage=replace(model.coverage, retrieval_complete=False))
    elif change == "boolean_schema":
        model = replace(model, schema_version=True)
    elif change == "integer_coverage":
        model = replace(model, coverage=replace(model.coverage, retrieval_complete=1))
    elif change == "integer_domain_coverage":
        model = replace(model, coverage=replace(model.coverage, domain_coverage_complete=1))
    else:
        model = replace(model, schema_version=2)
    checked = evaluate(bundle=bundle, model=model, gold=gold)
    assert not checked.binding_valid and checked.failure_reason == "input_binding_invalid"


@pytest.mark.parametrize("change", ["hash", "duplicate_id"])
def test_bundle_integrity_is_not_inferred_from_matching_quote(change):
    bundle, _, _ = fixture()
    first = replace(bundle.evidence[0], **(
        {"content_sha256": "0" * 64} if change == "hash" else {"evidence_id": "synthetic-2"}))
    checked = evaluate(bundle=replace(bundle, evidence=(first, bundle.evidence[1])))
    assert not checked.binding_valid and checked.failure_reason == "input_binding_invalid"


def test_policy_omission_of_model_domain_metadata_does_not_expand_or_deny_user_citations():
    _, model, _ = fixture()
    model = replace(model, evidence=tuple(replace(item, domain_ids=None) for item in model.evidence))
    assert evaluate(model=model).failure_reason is None


def test_required_sources_cannot_be_satisfied_by_pool_presence_or_an_uncited_gold():
    bundle, model, gold = fixture()
    gold["other"] = {"chunk": "c2", "sha256": bundle.evidence[1].content_sha256, "clause": "共同语句。"}
    assert evaluate(gold=gold).required_clauses == (("rule", True), ("other", False))
    assert evaluate([point(), point(2)], gold=gold).required_clauses == (("rule", True), ("other", True))
    # Empty/mismatched gold never silently closes the coverage check.
    with pytest.raises(ValueError, match="^stage_b.invalid_source_gold$"):
        evaluate(gold={})


def test_identical_content_in_a_different_chunk_is_not_the_expected_source():
    bundle, model, gold = fixture()
    first = bundle.evidence[0]
    duplicate = replace(bundle.evidence[1], content=first.content, content_sha256=first.content_sha256)
    bundle = replace(bundle, evidence=(first, duplicate))
    model = replace(model, evidence=(model.evidence[0], replace(model.evidence[1], content=first.content)))
    assert evaluate([point()], bundle=bundle, model=model, gold=gold).failure_reason is None
    wrong_source = evaluate([point(2)], bundle=bundle, model=model, gold=gold)
    assert wrong_source.binding_valid and wrong_source.required_clauses == (("rule", False),)
    assert wrong_source.failure_reason == "required_source_not_cited"


@pytest.mark.parametrize("change", ["sha", "empty_clause", "long_clause", "unknown_field", "name", "mapping", "nested_mapping"])
def test_invalid_gold_is_a_finite_harness_error_not_model_failure(change):
    _, _, gold = fixture()
    if change == "sha":
        gold["rule"]["sha256"] = "not-a-hash"
    elif change == "empty_clause":
        gold["rule"]["clause"] = ""
    elif change == "long_clause":
        gold["rule"]["clause"] = "x" * 513
    elif change == "name":
        gold = {"uncontrolled\nname": gold["rule"]}
    elif change == "mapping":
        gold = []
    elif change == "nested_mapping":
        gold = {"rule": None}
    else:
        gold["rule"]["extra"] = "not-allowed"
    with pytest.raises(ValueError, match="^stage_b.invalid_source_gold$"):
        evaluate(gold=gold)
