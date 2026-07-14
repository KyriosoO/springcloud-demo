package com.dylan.esquery.api.model.document;

import java.util.List;

/** 查询向量与 06 Provider/model safe binding。 */
public record DocumentQueryEmbeddingDto(
        List<Double> vector,
        int dimension,
        String providerBindingDigest) {
    public DocumentQueryEmbeddingDto {
        vector=List.copyOf(vector==null?List.of():vector);
        if(dimension<=0||vector.size()!=dimension||vector.stream().anyMatch(v->v==null||!Double.isFinite(v))
                ||providerBindingDigest==null||!providerBindingDigest.matches("[0-9a-f]{64}")){
            throw new IllegalArgumentException("document query embedding invalid");
        }
    }
}
