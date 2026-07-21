package com.dylan.agent.capability.document.acl;

public interface DocumentAclCurrentnessPort {
    DocumentAclCurrentnessDecision verifyScope(DocumentAclScopeCurrentnessRequest request);
    DocumentAclCurrentnessDecision verifyCandidates(DocumentAclCandidateCurrentnessRequest request);
}
