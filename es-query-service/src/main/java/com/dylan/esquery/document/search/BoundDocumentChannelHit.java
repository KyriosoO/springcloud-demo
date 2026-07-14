package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;

import java.math.BigDecimal;
import java.util.List;

/** RRF 前已完成 schema/source/ACL binding 校验的内部 hit。 */
public record BoundDocumentChannelHit(
        DocumentSearchChannel channel,
        int rank,
        BigDecimal esScore,
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
        Integer charStart,
        Integer charEnd,
        List<String> contextBefore,
        List<String> contextAfter) {
    public BoundDocumentChannelHit {
        contextBefore=List.copyOf(contextBefore==null?List.of():contextBefore);
        contextAfter=List.copyOf(contextAfter==null?List.of():contextAfter);
    }
}
