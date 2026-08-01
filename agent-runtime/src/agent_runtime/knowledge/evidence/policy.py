from __future__ import annotations

import hashlib
import json

from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, KnowledgePolicyCatalogError
from agent_runtime.knowledge.evidence.contracts import (
    EvidencePolicyDecision,
    EvidencePolicyDenial,
    KnowledgeEgressDisposition,
    KnowledgeEgressField,
    KnowledgeEvidenceBundle,
    KnowledgeSummaryInput,
    SummaryCoverageInput,
    SummaryEvidenceInput,
)

_ALL_FIELDS = frozenset(KnowledgeEgressField)
_DOMAIN_POLICY = {
    "tax.policy": ("knowledge.egress.tax_policy.v1", "1", _ALL_FIELDS, 4096),
    "tax.law": ("knowledge.egress.tax_law.v1", "1", _ALL_FIELDS, 4096),
}


class KnowledgeEvidenceEgressDecider:
    def decide(
        self,
        *,
        bundle: KnowledgeEvidenceBundle,
        catalog: KnowledgeEgressPolicyCatalog,
    ) -> EvidencePolicyDecision:
        inputs: list[SummaryEvidenceInput] = []
        documents: list[dict[str, str]] = []
        domain_ids: list[str] = []
        for index, evidence in enumerate(bundle.evidence, 1):
            try:
                document_policy, _ = catalog.resolve(
                    document_id=evidence.document_id,
                    policy_ref=evidence.policy_ref,
                    index_snapshot_id=evidence.index_snapshot_id,
                )
            except KnowledgePolicyCatalogError as exc:
                reason = EvidencePolicyDenial.POLICY_CONFLICT if "conflict" in str(exc) else EvidencePolicyDenial.POLICY_MISSING
                return EvidencePolicyDecision(allowed=False, denial_reason=reason)
            if document_policy.disposition is KnowledgeEgressDisposition.DENY:
                return EvidencePolicyDecision(allowed=False, denial_reason=EvidencePolicyDenial.DOCUMENT_DENIED)
            fields = set(_ALL_FIELDS) & set(document_policy.allowed_fields)
            max_content = min(4096, document_policy.max_content_code_points)
            for domain_id in evidence.domain_ids:
                domain = _DOMAIN_POLICY.get(domain_id)
                if domain is None:
                    return EvidencePolicyDecision(allowed=False, denial_reason=EvidencePolicyDenial.DOMAIN_DENIED)
                if domain_id not in domain_ids:
                    domain_ids.append(domain_id)
                fields &= set(domain[2])
                max_content = min(max_content, domain[3])
            if KnowledgeEgressField.CONTENT not in fields or len(evidence.content) > max_content:
                return EvidencePolicyDecision(allowed=False, denial_reason=EvidencePolicyDenial.DOCUMENT_DENIED)
            inputs.append(
                SummaryEvidenceInput(
                    evidence_ref=f"e{index}",
                    content=evidence.content,
                    domain_ids=evidence.domain_ids if KnowledgeEgressField.DOMAIN_IDS in fields else None,
                    title=evidence.source.title if KnowledgeEgressField.TITLE in fields else None,
                    document_number=evidence.source.document_number if KnowledgeEgressField.DOCUMENT_NUMBER in fields else None,
                    written_date=evidence.source.written_date.isoformat() if evidence.source.written_date is not None and KnowledgeEgressField.WRITTEN_DATE in fields else None,
                    material_type=evidence.source.material_type if KnowledgeEgressField.MATERIAL_TYPE in fields else None,
                )
            )
            documents.append(
                {
                    "documentId": evidence.document_id,
                    "policyRef": document_policy.policy_ref,
                    "policyVersion": document_policy.policy_version,
                    "indexSnapshotId": evidence.index_snapshot_id,
                }
            )
        summary_input = KnowledgeSummaryInput(
            schema_version=1,
            question=bundle.question_trace.minimized_question,
            coverage=SummaryCoverageInput(
                retrieval_complete=bundle.coverage.retrieval_complete,
                domain_coverage_complete=not bundle.coverage.missing_domain_ids,
            ),
            evidence=tuple(inputs),
        )
        snapshot_material = {
            "catalogVersion": catalog.snapshot.catalog_version,
            "authorityId": catalog.snapshot.authority_id,
            "exportId": catalog.snapshot.export_id,
            "sourceRevision": catalog.snapshot.source_revision,
            "domainPolicies": [
                {"domainId": domain_id, "policyRef": _DOMAIN_POLICY[domain_id][0], "policyVersion": _DOMAIN_POLICY[domain_id][1]}
                for domain_id in domain_ids
            ],
            "documents": documents,
        }
        snapshot_fingerprint = hashlib.sha256(
            json.dumps(snapshot_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return EvidencePolicyDecision(
            allowed=True,
            summary_input=summary_input,
            snapshot_fingerprint=snapshot_fingerprint,
        )
