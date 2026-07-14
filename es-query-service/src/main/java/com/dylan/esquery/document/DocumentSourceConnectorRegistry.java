package com.dylan.esquery.document;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Connector 候选一次性闭合；unknown/duplicate 均 fail closed。 */
public final class DocumentSourceConnectorRegistry {
    private final Map<String, DocumentSourceConnector> connectors;

    public DocumentSourceConnectorRegistry(List<DocumentSourceConnector> candidates) {
        Map<String, DocumentSourceConnector> indexed = new HashMap<>();
        for (DocumentSourceConnector connector : candidates == null ? List.<DocumentSourceConnector>of() : candidates) {
            String id = connector.connectorId();
            if (id == null || !id.matches("[a-z0-9-]{1,128}")) throw new IllegalArgumentException("invalid document source connector id");
            if (indexed.putIfAbsent(id, connector) != null) throw new IllegalArgumentException("duplicate document source connector: " + id);
        }
        connectors = Map.copyOf(indexed);
    }

    public DocumentSourceConnector require(String connectorId) {
        DocumentSourceConnector connector = connectors.get(connectorId);
        if (connector == null) throw new DocumentRebuildFailure("DOCUMENT_SOURCE_CONNECTOR_NOT_REGISTERED");
        return connector;
    }

    public void requireCatalogClosure(DocumentCorpusCatalog catalog) {
        catalog.snapshot().definitions().values().forEach(definition -> require(definition.sourceConnectorId()));
    }
}
