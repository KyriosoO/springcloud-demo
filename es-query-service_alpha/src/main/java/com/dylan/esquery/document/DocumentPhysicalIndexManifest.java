package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;

import java.time.Instant;

/** SUCCESS 前写入并回读的 immutable physical index manifest。 */
public record DocumentPhysicalIndexManifest(
        String physicalIndex,
        DocumentCorpusKeyDto corpusKey,
        DocumentSchemaRefDto schemaRef,
        String analyzerRef,
        String vectorPolicyRef,
        String chunkStrategyRef,
        String sourceSnapshotRef,
        String sourceSnapshotDigest,
        String taskId,
        long documentCount,
        long chunkCount,
        String indexContentDigest,
        Instant sealedAt,
        String manifestDigest) {
    public DocumentPhysicalIndexManifest {
        if (physicalIndex == null || !physicalIndex.startsWith("agent-doc-")
                || corpusKey == null || schemaRef == null || sealedAt == null
                || blank(analyzerRef) || blank(vectorPolicyRef) || blank(chunkStrategyRef)
                || blank(sourceSnapshotRef) || blank(taskId)
                || !digest(sourceSnapshotDigest) || !digest(indexContentDigest) || !digest(manifestDigest)
                || documentCount < 0 || chunkCount < 0) {
            throw new IllegalArgumentException("document physical index manifest invalid");
        }
    }

    private static boolean blank(String value) { return value == null || value.isBlank(); }
    private static boolean digest(String value) { return value != null && value.matches("[0-9a-f]{64}"); }
}
