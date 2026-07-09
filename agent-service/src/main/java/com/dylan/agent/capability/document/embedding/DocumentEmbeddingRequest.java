package com.dylan.agent.capability.document.embedding;

import java.time.Instant;
import java.util.List;

/** 文档查询向量生成请求。 */
public record DocumentEmbeddingRequest(
        String requestId,
        String queryText,
        List<String> queryVariants,
        String domain,
        String provider,
        String model,
        String expectedModel,
        int expectedDimension,
        Instant deadline) {

    public DocumentEmbeddingRequest(
            String requestId,
            String queryText,
            String domain,
            String model,
            Instant deadline) {
        this(requestId, queryText, queryText == null ? List.of() : List.of(queryText),
                domain, null, model, model, 0, deadline);
    }
}
