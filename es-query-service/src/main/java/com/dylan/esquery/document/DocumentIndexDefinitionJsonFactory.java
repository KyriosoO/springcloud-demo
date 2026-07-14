package com.dylan.esquery.document;

import java.util.LinkedHashMap;
import java.util.Map;

/** Typed schema 到 ES create-index body 的唯一 mapper。 */
public final class DocumentIndexDefinitionJsonFactory {
    public Map<String, Object> createBody(DocumentIndexDefinition definition, String taskId) {
        Map<String, Object> properties = new LinkedHashMap<>();
        for (String field : java.util.List.of("tenantId", "documentId", "documentVersion", "chunkId", "aclRef",
                "aclVersion", "visibility", "status", "userIds", "departmentIds", "roleIds", "attributeKeys",
                "chunkContentHash")) properties.put(field, Map.of("type", "keyword"));
        for (String field : java.util.List.of("chunkIndex", "charStart", "charEnd", "page")) properties.put(field, Map.of("type", "integer"));
        for (String field : java.util.List.of("content", "title", "section")) {
            properties.put(field, Map.of("type", "text", "analyzer", definition.analyzerRef()));
        }
        properties.put("safeSourceUri", Map.of("type", "keyword", "index", false));
        properties.put("sourceUpdatedAt", Map.of("type", "date"));
        for (DocumentBusinessFieldDefinition field : definition.businessFields()) {
            properties.put(field.name(), Map.of("type", field.type().name().toLowerCase()));
        }
        if (definition.vectorEnabled()) {
            properties.put("embedding", Map.of("type", "dense_vector", "dims", definition.vectorDimension(),
                    "similarity", definition.vectorSimilarity(), "index", true));
        }
        Map<String, Object> mappings = new LinkedHashMap<>();
        mappings.put("dynamic", "strict");
        mappings.put("_source", definition.vectorEnabled() ? Map.of("excludes", java.util.List.of("embedding")) : Map.of());
        mappings.put("_meta", Map.of("agent_document_build", Map.of("taskId", taskId, "sealed", false)));
        mappings.put("properties", Map.copyOf(properties));
        Map<String, Object> settings = "standard".equals(definition.analyzerRef()) ? Map.of()
                : Map.of("analysis", Map.of("analyzer", Map.of(
                definition.analyzerRef(), Map.of("type", "standard"))));
        return Map.of("settings", settings, "mappings", Map.copyOf(mappings));
    }
}
