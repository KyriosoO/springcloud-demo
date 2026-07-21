package com.dylan.esquery.api.model.document;

import java.util.List;

/** Document 专用 strict response envelope。 */
public record HybridSearchResponse(
        DocumentSearchResponseBinding binding,
        List<HybridSearchHit> hits,
        List<DocumentChannelResultSummary> channelResults,
        HybridRetrievalDiagnostics diagnostics) {
    public HybridSearchResponse {
        if(binding==null||diagnostics==null)throw new IllegalArgumentException("document hybrid response incomplete");
        hits=List.copyOf(hits==null?List.of():hits);
        channelResults=List.copyOf(channelResults==null?List.of():channelResults);
        if(channelResults.isEmpty()||diagnostics.returnedChunkCount()!=hits.size())throw new IllegalArgumentException("document hybrid response count mismatch");
    }
}
