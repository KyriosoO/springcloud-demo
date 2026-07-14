package com.dylan.esquery.api.model.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentProtectedFilterDto;

import java.util.List;

/** Document 专用 strict wire request；target 只能由 CorpusKey 在服务端解析。 */
public record HybridSearchRequest(
        DocumentCorpusKeyDto corpusKey,
        DocumentSearchExecutionBinding executionBinding,
        List<DocumentCallerFilterNode> callerFilters,
        DocumentProtectedFilterDto protectedFilter,
        String protectedFilterDigest,
        DocumentQueryPlan queryPlan,
        List<DocumentHybridChannelRequest> channels,
        HybridFusionRequest fusion,
        HybridDedupRequest dedup,
        HybridContextRequest context,
        DocumentSearchOperationMetadata operationMetadata) {
    public HybridSearchRequest {
        callerFilters=List.copyOf(callerFilters==null?List.of():callerFilters);
        channels=List.copyOf(channels==null?List.of():channels);
        if(corpusKey==null||executionBinding==null||protectedFilter==null||queryPlan==null||channels.isEmpty()
                ||fusion==null||dedup==null||context==null||operationMetadata==null){
            throw new IllegalArgumentException("document hybrid request incomplete");
        }
        if(protectedFilterDigest==null||!protectedFilterDigest.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("protectedFilterDigest invalid");
        if(!executionBinding.resourceLimit().equals(operationMetadata.resourceLimit()))throw new IllegalArgumentException("resource limit wire binding mismatch");
    }
}
