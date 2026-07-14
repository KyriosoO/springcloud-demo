package com.dylan.agent.adapter.api.document.provider;
import java.util.List;
public record DocumentUntrustedRerankPayload(List<DocumentRerankScoreItem> scores) {
    public DocumentUntrustedRerankPayload {
        scores=DocumentProviderContractValidation.list(scores,"scores",true);
        DocumentProviderContractValidation.uniqueText(scores.stream().map(DocumentRerankScoreItem::candidateId).toList(),"candidateId");
    }
    public record DocumentRerankScoreItem(String candidateId,double score,DocumentRerankReasonCode reasonCode) {
        public DocumentRerankScoreItem {
            DocumentProviderContractValidation.text(candidateId,"candidateId");
            if(!Double.isFinite(score))throw new IllegalArgumentException("rerank score must be finite");
            java.util.Objects.requireNonNull(reasonCode,"reasonCode must not be null");
        }
    }
}
