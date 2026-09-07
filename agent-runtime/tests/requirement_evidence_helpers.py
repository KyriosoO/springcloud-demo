"""Synthetic request-local evidence, never historical bodies or live gold."""
from dataclasses import replace

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeEvidenceRequirement, KnowledgeQuestionKind, KnowledgeRequirementKind,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceLimits, KnowledgeRequirementSummaryInput, KnowledgeRequirementSummaryOutput,
    KnowledgeSummaryPoint, SummaryOutcome, SummaryRequirementCoverage,
)
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeCandidate
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.retrieval_helpers import candidate


def requirement_input(*, count=3, merged=False):
    source = evidence_input()
    requirements = tuple(KnowledgeEvidenceRequirement(requirement_id=f"r{i}", domain_id="tax.policy", kind=kind, focus=focus)
        for i, (kind, focus) in enumerate(zip(
            (KnowledgeRequirementKind.SUBJECT_SCOPE, KnowledgeRequirementKind.RULE, KnowledgeRequirementKind.TEMPORAL_SCOPE),
            ("服务分类依据", "税务规则依据", "规则生效依据"), strict=True), 1))
    items = tuple(RankedKnowledgeCandidate(candidate=candidate(chunk=f"c{i}", rank=i, content=f"合成税务公开原文{i}。"),
        domain_ids=("tax.policy",), rank=i, rerank_score=float(-i), coverage_anchor=i <= (1 if merged else 3),
        requirement_ids=(tuple(r.requirement_id for r in requirements) if merged else (f"r{i}",)) if i <= (1 if merged else 3) else (),
    ) for i in range(1, count + 1))
    return replace(source, quality_version=KNOWLEDGE_QUALITY_VERSION_V3, question_kind=KnowledgeQuestionKind.APPLICABILITY,
        evidence_requirements=requirements, batch=replace(source.batch, candidates=items))


def select(source, *, limits=None):
    return DeterministicEvidenceSelector().select(candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question=source.original_question, limits=limits or KnowledgeEvidenceLimits.quality_v3())


def bound_input(source=None, *, catalog=None):
    source = source or requirement_input()
    bundle = select(source).bundle
    assert bundle is not None
    allowed = KnowledgeEvidenceEgressDecider().decide(bundle=bundle, catalog=catalog or synthetic_catalog()).summary_input
    assert allowed is not None
    value = KnowledgeRequirementSummaryInput(schema_version=2, question=allowed.question, coverage=allowed.coverage,
        evidence=allowed.evidence, requirements=source.evidence_requirements)
    return source, bundle, value


def output_for(value, *, merged=False):
    refs = ("e1",) if merged else tuple(f"e{i}" for i in range(1, len(value.requirements) + 1))
    return KnowledgeRequirementSummaryOutput(outcome=SummaryOutcome.ANSWER,
        points=tuple(KnowledgeSummaryPoint(evidence_ref=ref, quote=value.evidence[int(ref[1:]) - 1].content) for ref in refs),
        coverage=tuple(SummaryRequirementCoverage(requirement_id=item.requirement_id,
            evidence_refs=("e1" if merged else f"e{i}",)) for i, item in enumerate(value.requirements, 1)))
