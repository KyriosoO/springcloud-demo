package com.dylan.agent.adapter.api.document.provider;
import java.util.List;
public record DocumentEmbeddingInputProjection(List<String> texts) {
    public DocumentEmbeddingInputProjection {
        texts=DocumentProviderContractValidation.list(texts,"texts",false);
        texts.forEach(value->DocumentProviderContractValidation.text(value,"embedding text"));
    }
}
