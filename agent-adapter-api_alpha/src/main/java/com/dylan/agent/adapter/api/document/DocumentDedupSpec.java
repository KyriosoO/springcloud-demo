package com.dylan.agent.adapter.api.document;

/** 文档/分块选择上限；策略固定为 security-bound document selection。 */
public record DocumentDedupSpec(int maxReturnedDocuments, int maxChunksPerDocument) {
    public DocumentDedupSpec {
        if (maxReturnedDocuments <= 0 || maxChunksPerDocument <= 0) {
            throw new IllegalArgumentException("document dedup spec invalid");
        }
    }
}
