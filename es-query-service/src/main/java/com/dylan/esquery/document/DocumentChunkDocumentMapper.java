package com.dylan.esquery.document;

import java.util.LinkedHashMap;
import java.util.Map;

/** Typed chunk 到 ES schema v3 文档的唯一内部 mapper。 */
public final class DocumentChunkDocumentMapper {
    public Map<String, Object> toDocument(NormalizedDocumentChunk chunk) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("tenantId", chunk.tenantId()); value.put("documentId", chunk.documentId());
        value.put("documentVersion", chunk.documentVersion()); value.put("chunkId", chunk.chunkId());
        value.put("chunkIndex", chunk.chunkIndex()); value.put("charStart", chunk.charStart()); value.put("charEnd", chunk.charEnd());
        value.put("content", chunk.content()); optional(value, "title", chunk.title()); optional(value, "section", chunk.section());
        optional(value, "page", chunk.page()); optional(value, "safeSourceUri", chunk.safeSourceUri());
        optional(value, "sourceUpdatedAt", chunk.sourceUpdatedAt() == null ? null : chunk.sourceUpdatedAt().toString());
        value.put("chunkContentHash", chunk.chunkContentHash()); value.put("status", chunk.status());
        value.put("aclRef", chunk.aclRef()); value.put("aclVersion", chunk.aclVersion()); value.put("visibility", chunk.visibility());
        value.put("userIds", chunk.userIds()); value.put("departmentIds", chunk.departmentIds());
        value.put("roleIds", chunk.roleIds()); value.put("attributeKeys", chunk.attributeKeys());
        for (DocumentBusinessFieldValue field : chunk.businessFields()) value.put(field.name(), field.value());
        if (!chunk.embedding().isEmpty()) value.put("embedding", chunk.embedding());
        return Map.copyOf(value);
    }

    private static void optional(Map<String, Object> target, String field, Object value) {
        if (value != null) target.put(field, value);
    }
}
