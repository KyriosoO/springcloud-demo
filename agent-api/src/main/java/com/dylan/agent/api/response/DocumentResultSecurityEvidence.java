package com.dylan.agent.api.response;

import java.time.Instant;
import java.util.List;

/** Handler final currentness 决定的内部 sidecar；公共序列化必须忽略。 */
public record DocumentResultSecurityEvidence(
        String outcome,
        String invocationId,
        String operationId,
        String permissionVersion,
        String candidateSetDigest,
        String authorizationBindingDigest,
        String resourceLimitDigest,
        String aclDecisionVersion,
        String emergencyViewVersion,
        Instant checkedAt,
        Instant validUntil,
        String decisionDigest,
        String reasonCode,
        List<DocumentResultCandidateSecurityEvidence> candidates,
        List<String> evidenceRefs) {
    public DocumentResultSecurityEvidence {
        candidates = List.copyOf(candidates == null ? List.of() : candidates);
        evidenceRefs = List.copyOf(evidenceRefs == null ? List.of() : evidenceRefs);
    }
}
