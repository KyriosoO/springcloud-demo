package com.dylan.agent.capability.document.embedding;

import java.time.Instant;

/** 文档查询向量生成请求。 */
public record DocumentEmbeddingRequest(
        String requestId,
        String queryText,
        String domain,
        String model,
        Instant deadline) {
}
