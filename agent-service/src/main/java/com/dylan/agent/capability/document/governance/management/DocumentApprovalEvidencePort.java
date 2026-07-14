package com.dylan.agent.capability.document.governance.management;

public interface DocumentApprovalEvidencePort {
    DocumentApprovalEvidence requireApproval(
            DocumentApprovalVerificationRequest request,
            DocumentManagementAuthorizationContext context);
}
