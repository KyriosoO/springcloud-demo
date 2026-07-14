package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentIndexAccessGuardTest {

    private final DocumentIndexAccessGuard guard = new DocumentIndexAccessGuard(new DocumentCorpusCatalog(List.of(
            new DocumentCorpusDefinition(
                    new DocumentCorpusKeyDto("policy", "document"),
                    "agent-doc-policy-document-read",
                    new DocumentSchemaRefDto("document", "3", "a".repeat(64)),
                    "ik-v1", "vector-v1", "chunk-v1", "connector-v1", Set.of("title")))));

    @Test
    void rejectsRegisteredAliasAndPhysicalDocumentIndex() {
        assertThatThrownBy(() -> guard.requireGenericTarget("agent-doc-policy-document-read"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
        assertThatThrownBy(() -> guard.requireGenericTarget("agent-doc-policy-document-s3-build"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
    }

    @Test
    void permitsNonDocumentTarget() {
        assertThatCode(() -> guard.requireGenericTarget("orders-v2")).doesNotThrowAnyException();
    }
}
