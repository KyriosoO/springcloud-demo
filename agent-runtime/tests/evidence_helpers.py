from __future__ import annotations

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount,
    KnowledgeEvidenceInput,
    PathRef,
    RetrievalCoverage,
    RetrievalPath,
)
from dataclasses import replace

from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, canonical_policy_fingerprint
from agent_runtime.knowledge.evidence.contracts import (
    DocumentPolicyBinding,
    KnowledgeEgressDisposition,
    KnowledgeEgressField,
    KnowledgeEgressPolicy,
    PolicyCatalogSnapshot,
)
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch, RankedKnowledgeCandidate
from agent_runtime.model.question_policy import QUESTION_EGRESS_POLICY_VERSION
from tests.retrieval_helpers import candidate


def evidence_input(*, question_denied: bool = False) -> KnowledgeEvidenceInput[RankedKnowledgeBatch]:
    item = candidate()
    batch = RankedKnowledgeBatch(
        candidates=(RankedKnowledgeCandidate(candidate=item, domain_ids=("tax.policy",), rerank_score=1.0, rank=1),),
        profile_version="tax-knowledge-search-v1", index_snapshot_ids=("a" * 64,),
    )
    return KnowledgeEvidenceInput(
        original_question="现行增值税政策是什么",
        selected_query="现行增值税政策",
        selected_domain_ids=("tax.policy",),
        coverage=RetrievalCoverage(
            successful_paths=(
                PathRef(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD),
                PathRef(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR),
            ),
            no_result_paths=(), failed_paths=(),
            candidate_count_by_domain=(DomainCandidateCount(logical_domain_id="tax.policy", count=1),),
            complete=True,
        ),
        question_policy_version=QUESTION_EGRESS_POLICY_VERSION,
        question_egress_denied=question_denied,
        batch=batch,
    )


def synthetic_catalog(*, disposition: KnowledgeEgressDisposition = KnowledgeEgressDisposition.ALLOW_MINIMAL) -> KnowledgeEgressPolicyCatalog:
    fields = frozenset(KnowledgeEgressField) if disposition is KnowledgeEgressDisposition.ALLOW_MINIMAL else frozenset()
    maximum = 4096 if disposition is KnowledgeEgressDisposition.ALLOW_MINIMAL else 0
    snapshot = PolicyCatalogSnapshot(
        schema_version=1, catalog_version="synthetic-v1", authority_id="synthetic-authority",
        export_id="synthetic-export", source_revision="synthetic-revision", source_sha256="b" * 64,
        canonical_fingerprint="0" * 64,
        policies=(KnowledgeEgressPolicy(
            policy_ref="policy-doc-v1", policy_version="1", disposition=disposition,
            allowed_fields=fields, max_content_code_points=maximum,
        ),),
        bindings=(DocumentPolicyBinding(
            document_id="d1", policy_ref="policy-doc-v1", policy_version="1",
            allowed_index_snapshot_ids=frozenset({"a" * 64}),
        ),),
    )
    snapshot = replace(snapshot, canonical_fingerprint=canonical_policy_fingerprint(snapshot))
    return KnowledgeEgressPolicyCatalog(snapshot)
