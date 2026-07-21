package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.adapter.api.document.DocumentEmbeddingBindingReference;
import java.util.List;
public record DocumentUntrustedEmbeddingPayload(
        List<List<Float>> vectors,
        int dimension,
        DocumentEmbeddingBindingReference bindingReference) {
    public DocumentUntrustedEmbeddingPayload {
        if(dimension<=0)throw new IllegalArgumentException("embedding dimension must be positive");
        if(bindingReference==null||bindingReference.dimension()!=dimension)
            throw new IllegalArgumentException("embedding binding reference mismatch");
        vectors=DocumentProviderContractValidation.list(vectors,"vectors",false).stream()
                .map(vector->DocumentProviderContractValidation.list(vector,"vector",false)).toList();
        if(vectors.stream().anyMatch(vector->vector.size()!=dimension
                ||vector.stream().anyMatch(value->value==null||!Float.isFinite(value)))){
            throw new IllegalArgumentException("embedding vector invalid");
        }
    }
}
