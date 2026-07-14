package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.service.EsIndexAliasService;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentIndexAccessGuardTest {

    private final EsIndexAliasService aliases = mock(EsIndexAliasService.class);
    private final DocumentIndexAccessGuard guard = new DocumentIndexAccessGuard(new DocumentCorpusCatalog(List.of(
            new DocumentCorpusDefinition(
                    new DocumentCorpusKeyDto("policy", "document"),
                    "agent-doc-policy-document-read",
                    new DocumentSchemaRefDto("document", "3", "a".repeat(64)),
                    "ik-v1", "vector-v1", "chunk-v1", "connector-v1", Set.of("title")))), aliases);

    @Test
    void rejectsRegisteredAliasAndPhysicalDocumentIndex() {
        assertThatThrownBy(() -> guard.requireGenericTarget("agent-doc-policy-document-read"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
        assertThatThrownBy(() -> guard.requireGenericTarget("agent-doc-policy-document-s3-build"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
    }

    @Test
    void permitsNonDocumentTarget() throws Exception {
        when(aliases.readCurrent("orders-v2"))
                .thenReturn(new EsIndexAliasService.AliasTargetView("orders-v2", List.of()));
        assertThatCode(() -> guard.requireGenericTarget("orders-v2")).doesNotThrowAnyException();
    }

    @Test
    void rejectsIndirectAliasAndWildcardTargets() throws Exception {
        when(aliases.readCurrent("orders-read"))
                .thenReturn(new EsIndexAliasService.AliasTargetView(
                        "orders-read", List.of("agent-doc-policy-document-s3-build")));

        assertThatThrownBy(() -> guard.requireGenericTarget("orders-read"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
        assertThatThrownBy(() -> guard.requireGenericTarget("*"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
        assertThatThrownBy(() -> guard.requireGenericTarget("orders-v2,agent-doc-policy-document-s3-build"))
                .isInstanceOf(DocumentIndexAccessGuard.DocumentSpecializedEndpointRequiredException.class);
    }
}
