package com.dylan.agent.adapter.api.document;

/** 06 Provider/model/version/dimension 的安全摘要绑定。 */
public record DocumentEmbeddingBindingReference(String canonicalDigest,int dimension){
    public DocumentEmbeddingBindingReference{if(canonicalDigest==null||!canonicalDigest.matches("[0-9a-f]{64}")||dimension<=0)throw new IllegalArgumentException("embedding binding invalid");}
}
