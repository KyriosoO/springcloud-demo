package com.dylan.esquery.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentChunkSchemaValidatorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentChunkSchemaValidator validator = new DocumentChunkSchemaValidator();

    @Test
    void acceptsValidDocumentChunkFixture() throws Exception {
        assertThatCode(() -> validator.validate("agent-doc-policy", validDocument()))
                .doesNotThrowAnyException();
    }

    @Test
    void acceptsV2Chunk() throws Exception {
        assertThatCode(() -> validator.validate("agent-doc-tax-policy-v2", validV2Document()))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsMissingAclProjectionAndInvalidVisibility() throws Exception {
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

    @Test
    void rejectsMissingMaterialTypeAndRetrievalProfileForV2Chunk() throws Exception {
        Map<String, Object> missingMaterialType = validV2Document();
        missingMaterialType.remove("materialType");

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", missingMaterialType))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("materialType");

        Map<String, Object> missingProfile = validV2Document();
        missingProfile.remove("retrievalProfile");

        assertThatThrownBy(() -> validator.validate("agent-doc-tax-policy-v2", missingProfile))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalProfile");
    }

    private Map<String, Object> validDocument() throws IOException {
        return objectMapper.readValue(
                getClass().getResourceAsStream("/fixtures/document/valid-document-chunk.json"),
                new TypeReference<>() {
                });
    }

    private Map<String, Object> validV2Document() throws IOException {
        return objectMapper.readValue(
                getClass().getResourceAsStream("/fixtures/document/valid-document-chunk-v2.json"),
                new TypeReference<>() {
                });
    }
}
