package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;

import java.util.Set;

/** Corpus Catalog 中一个语料的唯一不可变定义。 */
public record DocumentCorpusDefinition(
        DocumentCorpusKeyDto corpusKey,
        String readAlias,
        DocumentSchemaRefDto schemaRef,
        String analyzerRef,
        String vectorPolicyRef,
        String chunkStrategyRef,
        String sourceConnectorId,
        Set<String> indexedBusinessFields) {
    public DocumentCorpusDefinition {
        if (corpusKey == null || schemaRef == null) throw new IllegalArgumentException("corpusKey/schemaRef must not be null");
        if (readAlias == null || !readAlias.matches("agent-doc-[a-z0-9-]+-read") || readAlias.length() > 128) throw new IllegalArgumentException("invalid document readAlias");
        if (analyzerRef == null || analyzerRef.isBlank() || vectorPolicyRef == null || vectorPolicyRef.isBlank()
                || chunkStrategyRef == null || chunkStrategyRef.isBlank() || sourceConnectorId == null || sourceConnectorId.isBlank()) {
            throw new IllegalArgumentException("document corpus references must not be blank");
        }
        indexedBusinessFields = Set.copyOf(indexedBusinessFields == null ? Set.of() : indexedBusinessFields);
    }
}
