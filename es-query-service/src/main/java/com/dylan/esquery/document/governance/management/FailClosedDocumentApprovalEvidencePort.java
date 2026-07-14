package com.dylan.esquery.document.governance.management;

public final class FailClosedDocumentApprovalEvidencePort implements DocumentApprovalEvidencePort {
    @Override public DocumentApprovalEvidence requireApproval(DocumentApprovalVerificationRequest request,DocumentManagementAuthorizationContext context){throw new SecurityException("document governance approval adapter unavailable");}
}
