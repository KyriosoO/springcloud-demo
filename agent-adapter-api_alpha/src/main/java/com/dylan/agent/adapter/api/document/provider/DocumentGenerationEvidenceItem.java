package com.dylan.agent.adapter.api.document.provider;

public record DocumentGenerationEvidenceItem(
        String citationId,
        String title,
        String section,
        Integer page,
        String text) {
    public DocumentGenerationEvidenceItem {
        DocumentProviderContractValidation.text(citationId,"citationId");
        if(!citationId.matches("C[1-9][0-9]{0,9}"))throw new IllegalArgumentException("citationId is not canonical");
        if(title!=null)DocumentProviderContractValidation.text(title,"title");
        if(section!=null)DocumentProviderContractValidation.text(section,"section");
        if(page!=null&&page<=0)throw new IllegalArgumentException("page must be positive");
        DocumentProviderContractValidation.text(text,"text");
    }
}
