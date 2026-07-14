package com.dylan.agent.adapter.api.document;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
public record DocumentCandidateSecurityBinding(String invocationId,String requestCorrelationId,String registrationIdentity,DocumentCorpusKey corpusKey,DocumentTargetBindingReference targetBinding,String protectedFilterDigest,String aclEvidenceDigest,DocumentAclObjectRef aclObjectRef,String profileProjectionDigest,ResourceLimitReference resourceLimitReference) {
    public DocumentCandidateSecurityBinding {
        if(blank(invocationId)||blank(requestCorrelationId)||blank(registrationIdentity)||corpusKey==null
                ||targetBinding==null||aclObjectRef==null||resourceLimitReference==null
                ||!digest(protectedFilterDigest)||!digest(aclEvidenceDigest)||!digest(profileProjectionDigest))
            throw new IllegalArgumentException("document candidate security binding invalid");
    }
    private static boolean blank(String value){return value==null||value.isBlank();}
    private static boolean digest(String value){return value!=null&&value.matches("[0-9a-f]{64}");}
}
