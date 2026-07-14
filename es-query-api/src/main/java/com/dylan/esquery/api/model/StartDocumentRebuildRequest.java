package com.dylan.esquery.api.model;

/** Document 专用 FULL_SNAPSHOT rebuild 请求；不允许 URL、target 或自由参数。 */
public record StartDocumentRebuildRequest(
        String requestId,
        String idempotencyKey,
        SourceSnapshotRef sourceSnapshotRef,
        DocumentSchemaRefDto expectedSchemaRef,
        Long expectedDocumentCount) {
    public StartDocumentRebuildRequest {
        if (requestId == null || requestId.isBlank()) throw new IllegalArgumentException("requestId must not be blank");
        if (idempotencyKey == null || idempotencyKey.isBlank()) throw new IllegalArgumentException("idempotencyKey must not be blank");
        if (sourceSnapshotRef == null) throw new IllegalArgumentException("sourceSnapshotRef must not be null");
        if (expectedSchemaRef == null) throw new IllegalArgumentException("expectedSchemaRef must not be null");
        if (expectedDocumentCount != null && expectedDocumentCount < 0) throw new IllegalArgumentException("expectedDocumentCount must not be negative");
    }
}
