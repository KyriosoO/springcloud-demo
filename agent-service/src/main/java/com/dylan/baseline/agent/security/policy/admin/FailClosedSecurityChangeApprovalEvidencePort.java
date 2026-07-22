package com.dylan.baseline.agent.security.policy.admin;

/** 12A适配器未装配时的唯一默认行为。 */
public final class FailClosedSecurityChangeApprovalEvidencePort
        implements SecurityChangeApprovalEvidencePort {

    @Override
    public VerifiedApprovalEvidence verify(ApprovalVerificationRequest request) {
        throw new PolicyAdministrationException(
                "SECURITY_POLICY_APPROVAL_UNAVAILABLE",
                "independent security-change approval authority is unavailable");
    }
}
