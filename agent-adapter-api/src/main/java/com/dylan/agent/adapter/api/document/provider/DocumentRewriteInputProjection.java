package com.dylan.agent.adapter.api.document.provider;
public record DocumentRewriteInputProjection(String originalQuery,String language,int maxCandidates) {
    public DocumentRewriteInputProjection {
        DocumentProviderContractValidation.text(originalQuery, "originalQuery");
        DocumentProviderContractValidation.text(language, "language");
        if(maxCandidates<=0)throw new IllegalArgumentException("maxCandidates must be positive");
    }
}
