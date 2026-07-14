package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

public record DocumentProtectedFilterBinding(
        DocumentCorpusKey corpusKey,
        DocumentProtectedFilterNode root,
        String filterDigest,
        String aclEvidenceDigest,
        String profileProjectionDigest,
        ResourceLimitReference resourceLimitReference) {
    public DocumentProtectedFilterBinding { if(corpusKey==null||root==null||resourceLimitReference==null||filterDigest==null||aclEvidenceDigest==null||profileProjectionDigest==null) throw new IllegalArgumentException("protected filter binding must be complete"); }
}
