package com.dylan.agent.adapter.api.document;

import java.util.List;

/** 只绑定当前查询的一条有限向量及其 Provider safe binding。 */
public record DocumentQueryEmbedding(
        List<Double> vector,
        int dimension,
        DocumentEmbeddingBindingReference bindingReference) {
    public DocumentQueryEmbedding {
        vector = List.copyOf(vector == null ? List.of() : vector);
        if (dimension <= 0 || vector.size() != dimension || bindingReference == null
                || vector.stream().anyMatch(value -> value == null || !Double.isFinite(value))) {
            throw new IllegalArgumentException("document query embedding invalid");
        }
    }
}
