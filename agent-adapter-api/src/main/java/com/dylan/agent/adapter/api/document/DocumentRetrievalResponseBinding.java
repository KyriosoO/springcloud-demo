package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

/** Adapter 已复核的专用响应完整性绑定。 */
public record DocumentRetrievalResponseBinding(
        String requestCorrelationId,
        String operationId,
        DocumentCorpusKey corpusKey,
        DocumentTargetBindingReference targetBinding,
        String profileProjectionDigest,
        ResourceLimitReference resourceLimitReference,
        String authorizationBindingDigest,
        String protectedFilterDigest,
        String aclEvidenceDigest) {
    public DocumentRetrievalResponseBinding {
        if(requestCorrelationId==null||requestCorrelationId.isBlank()||operationId==null||operationId.isBlank()
                ||corpusKey==null||targetBinding==null||resourceLimitReference==null)throw new IllegalArgumentException("document response binding incomplete");
    }
}
