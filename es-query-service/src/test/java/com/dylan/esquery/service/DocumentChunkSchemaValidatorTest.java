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

    private Map<String, Object> validDocument() throws IOException {
        return objectMapper.readValue(
                getClass().getResourceAsStream("/fixtures/document/valid-document-chunk.json"),
                new TypeReference<>() {
                });
    }
}
