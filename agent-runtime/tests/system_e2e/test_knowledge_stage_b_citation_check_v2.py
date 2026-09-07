from dataclasses import replace
import json

import pytest

from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, KnowledgeSummaryInput
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator
from tests.requirement_evidence_helpers import bound_input, output_for, requirement_input
from tests.system_e2e.knowledge_stage_b_citation_check import check_citations as check_v1
from tests.system_e2e.knowledge_stage_b_citation_check_v2 import CHECK_VERSION, check_citations


def setup():
    source, bundle, value = bound_input()
    output = RequirementCoverageValidator().validate(output=output_for(value), requirements=source.evidence_requirements,
        summary_input=value, bundle=bundle)
    result = ExtractiveSummaryValidator().validate(output=output, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())
    points = [{"quote": p["quote"], "citation": dict(p["citation"], domainIds=list(p["citation"]["domainIds"]))} for p in result.domain_result["points"]]
    gold = {f"clause_{i}": {"chunk": e.chunk_id, "sha256": e.content_sha256, "clause": e.content} for i, e in enumerate(bundle.evidence, 1)}
    return bundle, value, points, gold


def test_v2_accepts_actual_new_input_while_v1_stays_schema_one_only():
    bundle, value, points, gold = setup()
    assert not check_v1(bundle=bundle, summary_input=value, points=points, required=gold).binding_valid
    result = check_citations(bundle=bundle, summary_input=value, points=points, required=gold)
    assert CHECK_VERSION == "stage-b-citation-binding-v2" and result.binding_valid and all(passed for _, passed in result.required_clauses)


@pytest.mark.parametrize("fault", ["old_type", "bool_schema", "no_requirements", "wrong_requirement", "schema_three"])
def test_wrong_new_type_and_basic_requirement_shape_rejected(fault):
    bundle, value, points, gold = setup()
    if fault == "old_type": value = KnowledgeSummaryInput(schema_version=1, question=value.question, coverage=value.coverage, evidence=value.evidence)
    elif fault == "bool_schema": value = replace(value, schema_version=True)
    elif fault == "schema_three": value = replace(value, schema_version=3)
    elif fault == "no_requirements": value = replace(value, requirements=())
    else: value = replace(value, requirements=(replace(value.requirements[0], requirement_id="other"),) + value.requirements[1:])
    with pytest.raises(ValueError): check_citations(bundle=bundle, summary_input=value, points=points, required=gold)


@pytest.mark.parametrize("fault", ["title", "material", "date", "number", "body", "wrong_gold_chunk", "quote", "wrong_citation"])
def test_v2_keeps_source_checks_and_does_not_ignore_present_metadata(fault):
    bundle, value, points, gold = setup()
    if fault in {"title", "material", "date", "number", "body"}:
        key = {"title": "title", "material": "material_type", "date": "written_date", "number": "document_number", "body": "content"}[fault]
        value = replace(value, evidence=(replace(value.evidence[0], **{key: "changed"}),) + value.evidence[1:])
    elif fault == "wrong_gold_chunk": gold["clause_1"]["chunk"] = "other"
    elif fault == "quote": points[0]["quote"] = "wrong quote"
    elif fault == "wrong_citation": points[0]["citation"]["evidenceId"] = bundle.evidence[1].evidence_id
    result = check_citations(bundle=bundle, summary_input=value, points=points, required=gold)
    assert not result.binding_valid or not all(passed for _, passed in result.required_clauses)


def test_policy_omitted_metadata_is_never_recovered_during_projection(monkeypatch):
    import tests.system_e2e.knowledge_stage_b_citation_check_v2 as adapter
    bundle, value, points, gold = setup()
    value = replace(value, evidence=tuple(replace(e, domain_ids=None, title=None, material_type=None, document_number=None, written_date=None) for e in value.evidence))
    seen = []
    def capture(**kwargs):
        seen.append(kwargs["summary_input"])
        return check_v1(**kwargs)
    monkeypatch.setattr(adapter, "check_v1", capture)
    assert adapter.check_citations(bundle=bundle, summary_input=value, points=points, required=gold).binding_valid
    assert seen[0].evidence is value.evidence and seen[0].coverage is value.coverage
    assert all(set(item) == {"evidence_ref", "content"} for item in json.loads(requirement_summary_input_json(value))["evidence"])
