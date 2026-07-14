package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentSchemaRefDto;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Schema ref 精确解析，不按 index 名称或版本字符串猜测。 */
public final class DocumentIndexDefinitionRegistry {
    private final Map<DocumentSchemaRefDto, DocumentIndexDefinition> definitions;

    public DocumentIndexDefinitionRegistry(List<DocumentIndexDefinition> candidates) {
        Map<DocumentSchemaRefDto, DocumentIndexDefinition> values = new HashMap<>();
        for (DocumentIndexDefinition candidate : candidates == null ? List.<DocumentIndexDefinition>of() : candidates) {
            if (values.putIfAbsent(candidate.schemaRef(), candidate) != null) {
                throw new IllegalArgumentException("duplicate document index definition");
            }
        }
        definitions = Map.copyOf(values);
    }

    public DocumentIndexDefinition require(DocumentSchemaRefDto schemaRef) {
        DocumentIndexDefinition definition = definitions.get(schemaRef);
        if (definition == null) throw new IllegalStateException("DOCUMENT_SCHEMA_NOT_REGISTERED");
        return definition;
    }

    public void requireCorpusClosure(DocumentCorpusDefinition corpus) {
        DocumentIndexDefinition definition = require(corpus.schemaRef());
        if (!definition.analyzerRef().equals(corpus.analyzerRef())) throw new IllegalStateException("DOCUMENT_ANALYZER_BINDING_MISMATCH");
        if (!definition.businessFields().stream().map(DocumentBusinessFieldDefinition::name).collect(java.util.stream.Collectors.toSet())
                .equals(corpus.indexedBusinessFields())) throw new IllegalStateException("DOCUMENT_BUSINESS_SCHEMA_BINDING_MISMATCH");
    }
}
