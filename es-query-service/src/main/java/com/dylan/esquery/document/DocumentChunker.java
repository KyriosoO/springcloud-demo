package com.dylan.esquery.document;

import java.util.ArrayList;
import java.util.List;

/** 版本化字符窗口切分；不拆分 surrogate pair，输出稳定 offset 与 chunkId。 */
public final class DocumentChunker {
    private final int windowCodePoints;
    private final int overlapCodePoints;

    public DocumentChunker(int windowCodePoints, int overlapCodePoints) {
        if (windowCodePoints <= 0 || overlapCodePoints < 0 || overlapCodePoints >= windowCodePoints) {
            throw new IllegalArgumentException("document chunk window/overlap invalid");
        }
        this.windowCodePoints = windowCodePoints;
        this.overlapCodePoints = overlapCodePoints;
    }

    public List<NormalizedDocumentChunk> chunk(NormalizedDocument document, String strategyRef) {
        if (document == null || strategyRef == null || strategyRef.isBlank()) {
            throw new IllegalArgumentException("document/strategyRef must not be blank");
        }
        List<NormalizedDocumentChunk> chunks = new ArrayList<>();
        int total = document.content().codePointCount(0, document.content().length());
        int startCodePoint = 0;
        int index = 0;
        while (startCodePoint < total) {
            int endCodePoint = Math.min(total, startCodePoint + windowCodePoints);
            int start = document.content().offsetByCodePoints(0, startCodePoint);
            int end = document.content().offsetByCodePoints(0, endCodePoint);
            String content = document.content().substring(start, end);
            String chunkId = DocumentChunkCanonicalizer.chunkId(document, index, start, end, strategyRef);
            String contentHash = DocumentChunkCanonicalizer.contentHash(content, document.title(), document.section(), document.businessFields());
            chunks.add(new NormalizedDocumentChunk(document.tenantId(), document.documentId(), document.documentVersion(),
                    chunkId, index, start, end, content, document.title(), document.section(), document.page(),
                    document.safeSourceUri(), document.sourceUpdatedAt(), contentHash, document.status(), document.aclRef(),
                    document.aclVersion(), document.visibility(), document.userIds(), document.departmentIds(),
                    document.roleIds(), document.attributeKeys(), document.businessFields(), List.of()));
            if (endCodePoint == total) break;
            startCodePoint = endCodePoint - overlapCodePoints;
            index++;
        }
        return List.copyOf(chunks);
    }
}
