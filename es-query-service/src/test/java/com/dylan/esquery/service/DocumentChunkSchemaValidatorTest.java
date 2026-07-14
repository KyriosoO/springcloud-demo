package com.dylan.esquery.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentChunkSchemaValidatorTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentChunkSchemaValidator validator = new DocumentChunkSchemaValidator();

    @Test
    void acceptsStrictSchemaV3Chunk() throws Exception {
        assertThatCode(() -> validator.validate("ignored", validDocument())).doesNotThrowAnyException();
    }

    @Test
    void rejectsUnknownProfileFieldAndContentHashMismatch() throws Exception {
        Map<String,Object> profile = validDocument();profile.put("retrievalProfile", "legacy");
        assertThatThrownBy(() -> validator.validate("ignored", profile)).hasMessageContaining("prohibited");
        Map<String,Object> hash = validDocument();hash.put("chunkContentHash", "0".repeat(64));
        assertThatThrownBy(() -> validator.validate("ignored", hash)).hasMessageContaining("hash mismatch");
    }

    @Test
    void requiresClosedSortedAclPrincipals() throws Exception {
        Map<String,Object> missing = validDocument();missing.put("visibility", "DEPARTMENT");missing.put("userIds", List.of());
        assertThatThrownBy(() -> validator.validate("ignored", missing)).hasMessageContaining("departmentIds");
        Map<String,Object> unsorted = validDocument();unsorted.put("userIds", List.of("u-2", "u-1"));
        assertThatThrownBy(() -> validator.validate("ignored", unsorted)).hasMessageContaining("sorted");
    }

    private Map<String,Object> validDocument() throws Exception {
        return objectMapper.readValue(getClass().getResourceAsStream("/fixtures/document/valid-document-chunk.json"), new TypeReference<>() {});
    }
}
