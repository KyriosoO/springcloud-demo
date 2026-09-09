"""No I/O beyond the versioned fixture, no model or live service."""
from dataclasses import FrozenInstanceError
import json
from unittest.mock import patch

import pytest

from tests.evaluation.knowledge.retrieval_benchmark_dataset import PATH, load_dataset
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as base


def test_current_fixture_is_bounded_grouped_and_gold_never_becomes_a_query():
    dataset = load_dataset()
    assert len(dataset.cases) == 24 and len(dataset.sources) == 20
    assert dataset.limits == {"search": 54, "embedding": 27, "rerank": 29}
    assert sum(c.split == "holdout" for c in dataset.cases) == 8
    assert sum(len(c.domains) == 2 for c in dataset.cases) == 3
    assert sum("住宿" in c.question for c in dataset.cases) == 2
    before = base.SPECIFICATIONS, base.CASES, base.GOLD, base.LIMITS
    with patch.multiple(base, **dataset.probe_inputs()):
        for case, spec in zip(dataset.cases, base.SPECIFICATIONS, strict=True):
            original, plan = base.plan_for(spec)
            assert original == case.question
            assert all(i.query_text == original and i.candidate_limit == 20 for i in plan.items)
            assert plan.selected_domain_ids == case.domains
            serialized = str(base.asdict(plan))
            assert all(s.chunk_id not in serialized and s.sha256 not in serialized for s in dataset.sources)
    assert before == (base.SPECIFICATIONS, base.CASES, base.GOLD, base.LIMITS)
    with pytest.raises(FrozenInstanceError):
        dataset.cases[0].split = "holdout"


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(extra=True), lambda d: d.update(schemaVersion=True),
    lambda d: d.update(sourceReview="model_self_scored"), lambda d: d.update(bindingSha256="x"),
    lambda d: d["sources"].pop(), lambda d: d["cases"].pop(),
    lambda d: d["sources"][0].update(chunkId="../secret"),
    lambda d: d["sources"][0].update(sha256="G" * 64),
    lambda d: d["sources"][0].update(anchors=[]),
    lambda d: d["sources"][0].update(anchors=["x", "x"]),
    lambda d: d["sources"][0].update(domainId="employee"),
    lambda d: d["sources"][1].update(id=d["sources"][0]["id"]),
    lambda d: d["sources"][1].update(chunkId=d["sources"][0]["chunkId"]),
    lambda d: d["sources"][-1].update(family="lodging"),
    lambda d: d["cases"][0].update(question="bad\nquestion"),
    lambda d: d["cases"][0].update(question="a" * 257),
    lambda d: d["cases"][0].update(corpusState="missing"),
    lambda d: d["cases"][0].update(split="holdout"),
    lambda d: d["cases"][0].update(caseId="KRB-002"),
    lambda d: d["cases"][0].update(domains=["tax.policy", "tax.policy"]),
    lambda d: d["cases"][0].update(requiredSources=["absent"]),
    lambda d: d["cases"][0].update(requiredSources=["lodging", "lodging"]),
    lambda d: d["cases"][0].update(requiredSources=["vat_rate"]),
    lambda d: d["cases"][0]["requirements"].pop(),
    lambda d: d["cases"][0]["requirements"][0].update(kind="invented"),
    lambda d: d["cases"][0]["requirements"][0].update(extra="unapproved"),
    lambda d: d["cases"][0]["requirements"][0].update(domainId="employee"),
    lambda d: d["cases"][0]["requirements"][0].update(focus="增值税法2027年规定"),
])
def test_invalid_fixture_rejected_before_any_plan_or_outbound(mutation):
    value = json.loads(PATH.read_bytes())
    mutation(value)
    with pytest.raises(ValueError):
        load_dataset(json.dumps(value).encode())


@pytest.mark.parametrize("raw", [b"", b"x" * 131073, b'{"a":1,"a":2}', b'{"a":NaN}', b"null", b"[]"],
                         ids=["empty", "oversized", "duplicate", "nan", "null", "array"])
def test_strict_json_and_size(raw):
    with pytest.raises(ValueError):
        load_dataset(raw)
