package com.dylan.baseline.agent.security.policy.admin;

import java.time.Instant;

/** 默认失败关闭；04仅可提供受控非生产迁移实现，12A后续提供独立生产批准实现。 */
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
