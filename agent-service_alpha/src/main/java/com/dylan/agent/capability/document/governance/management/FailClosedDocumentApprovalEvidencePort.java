package com.dylan.agent.capability.document.governance.management;

/** 未配置受信change-system adapter时拒绝所有需要审批的管理写。 */
public final class FailClosedDocumentApprovalEvidencePort implements DocumentApprovalEvidencePort {
    @Override
    public DocumentApprovalEvidence requireApproval(
            DocumentApprovalVerificationRequest request,
            DocumentManagementAuthorizationContext context) {
        throw new SecurityException("document governance approval adapter is unavailable");
    }
}
