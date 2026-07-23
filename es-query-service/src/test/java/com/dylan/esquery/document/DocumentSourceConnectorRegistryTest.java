package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentSourceConnectorRegistryTest {
    @Test
    void catalogClosureRejectsUnregisteredConnectorAtStartup() {
        DocumentCorpusCatalog catalog = catalog("connector-v1");
        DocumentSourceConnectorRegistry registry = new DocumentSourceConnectorRegistry(List.of());

        assertThatThrownBy(() -> registry.requireCatalogClosure(catalog))
                .isInstanceOf(DocumentRebuildFailure.class)
                .hasMessageContaining("DOCUMENT_SOURCE_CONNECTOR_NOT_REGISTERED");
    }

    @Test
    void catalogClosureAcceptsExactlyRegisteredConnector() {
        DocumentSourceConnector connector = mock(DocumentSourceConnector.class);
        when(connector.connectorId()).thenReturn("connector-v1");
        DocumentSourceConnectorRegistry registry = new DocumentSourceConnectorRegistry(List.of(connector));

        assertThatCode(() -> registry.requireCatalogClosure(catalog("connector-v1")))
                .doesNotThrowAnyException();
    }

    private static DocumentCorpusCatalog catalog(String connectorId) {
        return new DocumentCorpusCatalog(List.of(new DocumentCorpusDefinition(
                new DocumentCorpusKeyDto("policy", "document"),
                "agent-doc-policy-document-read",
                new DocumentSchemaRefDto("document", "3", "a".repeat(64)),
                "standard", "disabled", "chunk-v1", connectorId, Set.of())));
    }
}
