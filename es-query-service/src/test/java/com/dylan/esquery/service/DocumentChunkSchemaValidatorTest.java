package com.dylan.esquery.service;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentChunkSchemaValidatorTest {

    private final DocumentChunkSchemaValidator validator = new DocumentChunkSchemaValidator();

    @Test
    void rejectsMissingAclProjectionAndInvalidVisibility() {
        Map<String, Object> document = validDocument();
        document.remove("aclVersion");

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", document))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("aclVersion");

        Map<String, Object> invalidVisibility = validDocument();
        invalidVisibility.put("visibility", "DEPARTMENT");
        invalidVisibility.remove("departmentIds");

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", invalidVisibility))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("departmentIds");
    }

    private Map<String, Object> validDocument() {
        Map<String, Object> document = new LinkedHashMap<>();
        document.put("tenantId", "tenant-1");
        document.put("corpusId", "policy_document");
        document.put("documentId", "doc-1");
        document.put("documentVersion", "v1");
        document.put("chunkId", "chunk-1");
        document.put("chunkIndex", 1);
        document.put("charStart", 0);
        document.put("charEnd", 10);
        document.put("title", "休假政策");
        document.put("content", "脱敏内容");
        document.put("snippet", "脱敏片段");
        document.put("aclRef", "acl-1");
        document.put("aclVersion", "acl-v1");
        document.put("visibility", "USER");
        document.put("userIds", List.of("u-1"));
        document.put("status", "ACTIVE");
        document.put("indexVersion", "idx-v1");
        document.put("contentHash", "sha256:abc");
        return document;
    }
}
