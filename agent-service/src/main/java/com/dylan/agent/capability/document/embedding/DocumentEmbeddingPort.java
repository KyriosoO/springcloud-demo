package com.dylan.agent.capability.document.embedding;

/** queryText 到 queryVector 的受控端口。 */
public interface DocumentEmbeddingPort {
    DocumentEmbeddingResult embed(DocumentEmbeddingRequest request);
}
