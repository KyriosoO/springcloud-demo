package com.dylan.agent.api.response;

/** 文档生成链路状态。 */
public enum DocumentGenerationStatus {
    DISABLED,
    SKIPPED,
    EMBEDDING_FAILED,
    RETRIEVAL_PARTIAL,
    PACKED,
    GENERATING,
    SUCCEEDED,
    FALLBACK,
    FAILED
}
