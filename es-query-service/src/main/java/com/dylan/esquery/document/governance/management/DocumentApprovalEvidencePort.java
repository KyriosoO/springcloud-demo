package com.dylan.esquery.document.governance.management;

public interface DocumentApprovalEvidencePort {
    DocumentApprovalEvidence requireApproval(DocumentApprovalVerificationRequest request,DocumentManagementAuthorizationContext context);
}
