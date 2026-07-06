package com.dylan.esquery.service;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentIndexDefinitionValidatorTest {

    private final DocumentIndexDefinitionValidator validator = new DocumentIndexDefinitionValidator();

    @Test
    void rejectsMappingMissingAclFields() {
        Map<String, Object> mapping = validMapping();
        properties(mapping).remove("aclVersion");

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", mapping))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("aclVersion");

        Map<String, Object> missingProjection = validMapping();
        properties(missingProjection).remove("userIds");

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", missingProjection))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("userIds");
    }

    @Test
    void rejectsDenseVectorDimensionMismatch() {
        Map<String, Object> mapping = validMapping();
        properties(mapping).put("embedding", Map.of("type", "dense_vector", "dims", 0));

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", mapping))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("dims");
    }

    private Map<String, Object> validMapping() {
        Map<String, Object> fields = new LinkedHashMap<>();
        for (String field : java.util.List.of(
                "tenantId", "corpusId", "documentId", "documentVersion", "chunkId",
                "chunkIndex", "charStart", "charEnd", "title", "content", "snippet",
                "aclRef", "aclVersion", "visibility", "departmentIds", "roleIds", "userIds",
                "attributeKeys", "status", "indexVersion", "contentHash")) {
            fields.put(field, Map.of("type", "keyword"));
        }
        return Map.of("mappings", Map.of("properties", fields));
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> properties(Map<String, Object> mapping) {
        return (Map<String, Object>) ((Map<String, Object>) mapping.get("mappings")).get("properties");
    }
}
