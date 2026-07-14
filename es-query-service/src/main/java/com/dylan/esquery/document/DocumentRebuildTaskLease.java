package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.api.model.SourceSnapshotRef;

import java.time.Instant;

/** Worker 获取的单版本 task lease。 */
public record DocumentRebuildTaskLease(
        String taskId, DocumentCorpusKeyDto corpusKey, String connectorId,
        SourceSnapshotRef sourceSnapshotRef, DocumentSchemaRefDto schemaRef,
        String targetPhysicalIndexSafeRef, Long expectedDocumentCount,
        ProtectedSourceCursor cursor, long documentsRead, long chunksIndexed, long bulkAttempts,
        long rowVersion, String leaseOwner, Instant leaseExpiresAt) {
}
