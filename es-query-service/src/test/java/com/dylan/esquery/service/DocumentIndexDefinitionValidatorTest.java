package com.dylan.esquery.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentIndexDefinitionValidatorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentIndexDefinitionValidator validator = new DocumentIndexDefinitionValidator();

    @Test
    void acceptsValidDocumentIndexDefinitionFixture() throws Exception {
        assertThatCode(() -> validator.validate("agent-doc-policy", validMapping()))
                .doesNotThrowAnyException();
    }

    @Test
    void acceptsV2Mapping() throws Exception {
        assertThatCode(() -> validator.validate("agent-doc-tax-policy-v2", validV2Mapping()))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsMappingMissingAclFields() throws Exception {
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
    void rejectsDenseVectorDimensionMismatch() throws Exception {
        Map<String, Object> mapping = validV2Mapping();
        properties(mapping).put("embedding", Map.of("type", "dense_vector", "dims", 0));

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", mapping))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("dims");
    }

    @Test
    void rejectsInvalidEmbeddingMapping() throws Exception {
        Map<String, Object> wrongType = validV2Mapping();
        properties(wrongType).put("embedding", Map.of("type", "float", "dims", 1024));

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", wrongType))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("dense_vector");

        Map<String, Object> missingDims = validV2Mapping();
        properties(missingDims).put("embedding", Map.of("type", "dense_vector"));

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", missingDims))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("dims");
    }

    @Test
    void rejectsTextOnlyFilterField() throws Exception {
        Map<String, Object> mapping = validMapping();
        properties(mapping).put("tenantId", Map.of("type", "text"));

        assertThatThrownBy(() -> validator.validate("agent-doc-policy", mapping))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("tenantId");
    }

    @Test
    void rejectsMissingV2ProfileFieldAndUnknownAnalyzer() throws Exception {
        Map<String, Object> missingProfile = validV2Mapping();
        properties(missingProfile).remove("retrievalProfile");

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", missingProfile))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalProfile");

        Map<String, Object> unknownAnalyzer = validV2Mapping();
        properties(unknownAnalyzer).put("content", Map.of("type", "text", "analyzer", "ik_max_word"));

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", unknownAnalyzer))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("analyzer");
    }

    private Map<String, Object> validMapping() throws IOException {
        return objectMapper.readValue(
                getClass().getResourceAsStream("/fixtures/document/valid-document-index-definition.json"),
                new TypeReference<>() {
                });
    }

    private Map<String, Object> validV2Mapping() throws IOException {
        return objectMapper.readValue(
                getClass().getResourceAsStream("/fixtures/document/valid-document-index-definition-v2.json"),
                new TypeReference<>() {
                });
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> properties(Map<String, Object> mapping) {
        return (Map<String, Object>) ((Map<String, Object>) mapping.get("mappings")).get("properties");
    }
}
