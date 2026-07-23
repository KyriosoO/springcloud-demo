package com.dylan.esquery.api.model.document;

import java.math.BigDecimal;
import java.util.List;

/** 仅包含 safe source、identity、RRF 与 security refs 的 Document hit。 */
public record HybridSearchHit(
        String candidateId,
        String documentId,
        String documentVersion,
        String chunkId,
        int chunkIndex,
        String aclRef,
        String aclVersion,
        String title,
        String sourceType,
        String section,
        Integer page,
        String sourceUri,
        String snippet,
        String content,
        String citationText,
        String generationText,
        List<String> contextBefore,
        List<String> contextAfter,
        Integer charStart,
        Integer charEnd,
        BigDecimal score,
        BigDecimal rrfScore,
        List<DocumentChannelRank> channelRanks) {
    public HybridSearchHit {
        for(String value:new String[]{candidateId,documentId,documentVersion,chunkId,aclRef,aclVersion}){
            if(value==null||value.isBlank())throw new IllegalArgumentException("document hit identity/security binding incomplete");
        }
        if(chunkIndex<0||score==null||rrfScore==null||score.signum()<0||rrfScore.signum()<0)throw new IllegalArgumentException("document hit score/index invalid");
        contextBefore=List.copyOf(contextBefore==null?List.of():contextBefore);
        contextAfter=List.copyOf(contextAfter==null?List.of():contextAfter);
        channelRanks=List.copyOf(channelRanks==null?List.of():channelRanks);
        if(channelRanks.isEmpty())throw new IllegalArgumentException("document hit channel ranks required");
    }
}
