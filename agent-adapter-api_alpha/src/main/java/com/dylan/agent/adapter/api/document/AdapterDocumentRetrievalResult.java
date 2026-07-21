package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;

import java.util.List;

/** Adapter 唯一检索候选结果；不含 final evidence/currentness 语义。 */
public record AdapterDocumentRetrievalResult(
        List<AclBoundDocumentHit> hits,
        AdapterDocumentRetrievalDiagnostics diagnostics,
        DocumentRetrievalResponseBinding binding,
        int requestedDocumentCount) {
    public AdapterDocumentRetrievalResult {
        hits=List.copyOf(hits==null?List.of():hits);
        if(diagnostics==null||binding==null||requestedDocumentCount<=0)throw new IllegalArgumentException("adapter document retrieval result incomplete");
    }
}
