package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.document.SafeDocumentCandidate;
import com.dylan.agent.api.response.DocumentResultCandidateSecurityEvidence;
import com.dylan.agent.api.response.DocumentResultSecurityEvidence;

import java.util.List;

/** final decision/Safe candidates 到公共 payload 内部 sidecar 的唯一 mapper。 */
public final class DocumentResultSecurityEvidenceMapper {
    public DocumentResultSecurityEvidence map(
            DocumentFinalCurrentnessDecision decision,
            List<SafeDocumentCandidate> candidates,
            List<String> evidenceRefs) {
        return new DocumentResultSecurityEvidence(
                decision.outcome().name(), decision.invocationId(), decision.operationId(),
                decision.permissionVersion(), decision.candidateSetDigest(), decision.authorizationBindingDigest(),
                decision.resourceLimitReference().canonicalDigest(), decision.aclDecisionVersion(),
                decision.emergencyViewVersion(), decision.checkedAt(), decision.validUntil(),
                decision.decisionDigest(), decision.reasonCode().name(),
                candidates.stream().map(this::candidate).toList(), evidenceRefs);
    }

    private DocumentResultCandidateSecurityEvidence candidate(SafeDocumentCandidate candidate) {
        var identity = candidate.identity();
        var binding = candidate.securityBinding();
        return new DocumentResultCandidateSecurityEvidence(
                candidate.candidateId(), identity.documentId(), identity.documentVersion(), identity.chunkId(),
                identity.chunkIndex(), binding.protectedFilterDigest(), binding.aclEvidenceDigest(),
                binding.aclObjectRef().aclRef(), binding.aclObjectRef().aclVersion(),
                binding.targetBinding().manifestDigest(), binding.targetBinding().attestationDigest(),
                binding.profileProjectionDigest(), binding.resourceLimitReference().canonicalDigest());
    }
}
