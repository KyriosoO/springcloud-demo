package com.dylan.agent.capability.document.embedding;

/** 默认关闭的 embedding 端口，防止未配置 provider 时误调用。 */
public final class DisabledDocumentEmbeddingPort implements DocumentEmbeddingPort {
    @Override
    public DocumentEmbeddingResult embed(DocumentEmbeddingRequest request) {
        throw new IllegalStateException("document embedding is disabled");
    }
}
