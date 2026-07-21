package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContext;

public interface DocumentEmergencyGateEvidenceIssuer {
    DocumentEmergencyGateEvidence issueForRollout(
            DocumentEmergencyGateEvidenceIssueRequest request,
            DocumentManagementAuthorizationContext authorizationContext);
}
