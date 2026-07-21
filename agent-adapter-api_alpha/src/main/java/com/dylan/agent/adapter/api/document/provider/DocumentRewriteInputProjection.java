package com.dylan.agent.adapter.api.document.provider;
public record DocumentRewriteInputProjection(String originalQuery,DocumentLanguage language,int maxCandidates) {
    public DocumentRewriteInputProjection {
        DocumentProviderContractValidation.text(originalQuery, "originalQuery");
        java.util.Objects.requireNonNull(language, "language must not be null");
        if(maxCandidates<=0)throw new IllegalArgumentException("maxCandidates must be positive");
    }
}
