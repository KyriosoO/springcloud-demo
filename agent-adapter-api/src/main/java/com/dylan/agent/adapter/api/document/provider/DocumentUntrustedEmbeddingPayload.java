package com.dylan.agent.adapter.api.document.provider;
import java.util.List;
public record DocumentUntrustedEmbeddingPayload(List<List<Float>> vectors,int dimension,String bindingReference) {
    public DocumentUntrustedEmbeddingPayload {
        if(dimension<=0)throw new IllegalArgumentException("embedding dimension must be positive");
        DocumentProviderContractValidation.digest(bindingReference,"bindingReference");
        vectors=DocumentProviderContractValidation.list(vectors,"vectors",false).stream()
                .map(vector->DocumentProviderContractValidation.list(vector,"vector",false)).toList();
        if(vectors.stream().anyMatch(vector->vector.size()!=dimension
                ||vector.stream().anyMatch(value->value==null||!Float.isFinite(value)))){
            throw new IllegalArgumentException("embedding vector invalid");
        }
    }
}
