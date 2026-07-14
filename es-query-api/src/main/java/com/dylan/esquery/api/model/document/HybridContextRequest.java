package com.dylan.esquery.api.model.document;

/** 单批 context window 参数。 */
public record HybridContextRequest(int beforeChunks,int afterChunks,int maxContextChars){
    public HybridContextRequest{if(beforeChunks<0||afterChunks<0||maxContextChars<0)throw new IllegalArgumentException("context invalid");}
}
