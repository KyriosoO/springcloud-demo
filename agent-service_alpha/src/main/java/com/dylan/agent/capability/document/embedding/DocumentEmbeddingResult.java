package com.dylan.agent.capability.document.embedding;

import java.util.List;

/** 文档查询向量生成结果。 */
public record DocumentEmbeddingResult(
        List<Double> queryVector,
        String embeddingModel,
        int dimension,
        String digest) {
}
