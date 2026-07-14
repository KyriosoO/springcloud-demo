package com.dylan.agent.adapter.api.document.provider;
import java.util.List;
public record DocumentRerankInputProjection(String queryText,List<DocumentRerankInputItem> items) {
    public DocumentRerankInputProjection {
        DocumentProviderContractValidation.text(queryText,"queryText");
        items=DocumentProviderContractValidation.list(items,"items",false);
        DocumentProviderContractValidation.uniqueText(items.stream().map(DocumentRerankInputItem::candidateId).toList(),"candidateId");
    }
    public record DocumentRerankInputItem(String candidateId,String title,String snippet){
        public DocumentRerankInputItem {
            DocumentProviderContractValidation.text(candidateId,"candidateId");
            if(title!=null)DocumentProviderContractValidation.text(title,"title");
            if(snippet!=null)DocumentProviderContractValidation.text(snippet,"snippet");
        }
    }
}
