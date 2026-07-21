package com.dylan.agent.adapter.api.document.provider;
import java.util.List;
public record DocumentUntrustedRewritePayload(List<String> candidates) {
    public DocumentUntrustedRewritePayload {
        candidates=DocumentProviderContractValidation.list(candidates,"candidates",true);
        candidates.forEach(value->DocumentProviderContractValidation.text(value,"rewrite candidate"));
    }
}
