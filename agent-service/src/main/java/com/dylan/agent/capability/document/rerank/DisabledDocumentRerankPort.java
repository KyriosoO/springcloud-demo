package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.AdapterDocumentResult;

/** 默认禁用 rerank，保持 RRF 排序结果。 */
public class DisabledDocumentRerankPort implements DocumentRerankPort {
    @Override
    public AdapterDocumentResult rerank(DocumentRerankRequest request) {
        return request == null ? new AdapterDocumentResult() : request.candidates();
    }
}
