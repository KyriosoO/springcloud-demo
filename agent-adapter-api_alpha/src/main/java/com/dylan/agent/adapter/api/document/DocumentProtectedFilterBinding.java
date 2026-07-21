package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

public record DocumentProtectedFilterBinding(
        DocumentCorpusKey corpusKey,
        DocumentProtectedFilterNode root,
        String filterDigest,
        String aclEvidenceDigest,
        String profileProjectionDigest,
    ResourceLimitReference resourceLimitReference) {
    public DocumentProtectedFilterBinding {
        if(corpusKey==null||root==null||resourceLimitReference==null
                ||!digest(filterDigest)||!digest(aclEvidenceDigest)||!digest(profileProjectionDigest))
            throw new IllegalArgumentException("protected filter binding must be complete");
    }
    private static boolean digest(String value){return value!=null&&value.matches("[0-9a-f]{64}");}
}
