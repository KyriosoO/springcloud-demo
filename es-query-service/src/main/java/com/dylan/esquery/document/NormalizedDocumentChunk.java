package com.dylan.esquery.document;

import java.time.Instant;
import java.util.List;

/** 可写入 schema v3 的 typed chunk。 */
public record NormalizedDocumentChunk(
        String tenantId, String documentId, String documentVersion, String chunkId,
        int chunkIndex, int charStart, int charEnd, String content,
        String title, String section, Integer page, String safeSourceUri, Instant sourceUpdatedAt,
        String chunkContentHash, String status, String aclRef, String aclVersion, String visibility,
        List<String> userIds, List<String> departmentIds, List<String> roleIds, List<String> attributeKeys,
        List<DocumentBusinessFieldValue> businessFields, List<Double> embedding) {
    public NormalizedDocumentChunk {
        userIds = List.copyOf(userIds); departmentIds = List.copyOf(departmentIds);
        roleIds = List.copyOf(roleIds); attributeKeys = List.copyOf(attributeKeys);
        businessFields = List.copyOf(businessFields); embedding = List.copyOf(embedding == null ? List.of() : embedding);
    }

    public NormalizedDocumentChunk withEmbedding(List<Double> vector) {
        return new NormalizedDocumentChunk(tenantId, documentId, documentVersion, chunkId, chunkIndex, charStart,
                charEnd, content, title, section, page, safeSourceUri, sourceUpdatedAt, chunkContentHash, status,
                aclRef, aclVersion, visibility, userIds, departmentIds, roleIds, attributeKeys, businessFields, vector);
    }
}
