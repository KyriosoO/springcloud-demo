package com.dylan.esquery.api.model.document;

/** security-bound document selection 参数。 */
public record HybridDedupRequest(int maxReturnedDocuments,int maxChunksPerDocument){
    public HybridDedupRequest{if(maxReturnedDocuments<=0||maxChunksPerDocument<=0)throw new IllegalArgumentException("dedup invalid");}
}
