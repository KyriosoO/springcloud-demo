package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;

import java.util.Map;

/** 原子发布的 immutable catalog snapshot。 */
public record DocumentCorpusCatalogSnapshot(
        String catalogVersion,
        String canonicalDigest,
        Map<DocumentCorpusKeyDto, DocumentCorpusDefinition> definitions) {
    public DocumentCorpusCatalogSnapshot {
        definitions = Map.copyOf(definitions);
    }
}
