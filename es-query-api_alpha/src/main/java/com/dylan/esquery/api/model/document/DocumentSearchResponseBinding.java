package com.dylan.esquery.api.model.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;

/** es-query 专用响应的端到端完整性绑定。 */
public record DocumentSearchResponseBinding(
        String requestCorrelationId,
        String operationId,
        DocumentCorpusKeyDto corpusKey,
        DocumentTargetBindingDto targetBinding,
        String profileProjectionDigest,
        ResourceLimitBindingDto resourceLimit,
        String authorizationBindingDigest,
        String protectedFilterDigest,
        String aclEvidenceDigest) {
    public DocumentSearchResponseBinding {
        if(requestCorrelationId==null||requestCorrelationId.isBlank()||operationId==null||operationId.isBlank()
                ||corpusKey==null||targetBinding==null||resourceLimit==null)throw new IllegalArgumentException("response binding incomplete");
        for(String value:new String[]{profileProjectionDigest,authorizationBindingDigest,protectedFilterDigest,aclEvidenceDigest}){
            if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("response digest invalid");
        }
    }
}
