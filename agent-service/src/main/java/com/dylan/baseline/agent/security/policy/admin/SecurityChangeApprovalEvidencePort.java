package com.dylan.baseline.agent.security.policy.admin;

import java.time.Instant;

/** 由12A提供实现；Agent只消费并校验不可伪造的独立批准证据。 */
public interface SecurityChangeApprovalEvidencePort {

    VerifiedApprovalEvidence verify(ApprovalVerificationRequest request);

    record ApprovalVerificationRequest(
            String approvalRef,
            String operation,
            String fromPolicyDigest,
            String toPolicyDigest,
            String changeClass,
            long expectedStateVersion,
            String actorRefDigest) {
    }

    record VerifiedApprovalEvidence(
            String approvalRef,
            String evidenceDigest,
            String operation,
            String fromPolicyDigest,
            String toPolicyDigest,
            String changeClass,
            long expectedStateVersion,
            String approverRefDigest,
            Instant validUntil) {
    }
}
