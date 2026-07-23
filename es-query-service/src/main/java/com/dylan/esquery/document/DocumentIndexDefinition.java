package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentSchemaRefDto;

import java.util.HashSet;
import java.util.List;

/** Registry 返回的 immutable typed schema；管理 caller 不提交 mapping。 */
public record DocumentIndexDefinition(
        DocumentSchemaRefDto schemaRef,
        String analyzerRef,
        Integer vectorDimension,
        String vectorSimilarity,
        List<DocumentBusinessFieldDefinition> businessFields) {
    public DocumentIndexDefinition {
        if (schemaRef == null || analyzerRef == null || analyzerRef.isBlank()) throw new IllegalArgumentException("document schema binding incomplete");
        if ((vectorDimension == null) != (vectorSimilarity == null)) throw new IllegalArgumentException("document vector schema binding incomplete");
        if (vectorDimension != null && vectorDimension <= 0) throw new IllegalArgumentException("document vector dimension invalid");
        businessFields = List.copyOf(businessFields == null ? List.of() : businessFields);
        if (new HashSet<>(businessFields.stream().map(DocumentBusinessFieldDefinition::name).toList()).size() != businessFields.size()) {
            throw new IllegalArgumentException("duplicate document business field definition");
        }
    }

    public boolean vectorEnabled() { return vectorDimension != null; }
}
