package com.dylan.agent.capability.document.profile;

/** security-bound document selection 的唯一去重策略参数。 */
public record DocumentDedupPolicy(int maxChunksPerDocument) {
    public DocumentDedupPolicy {
        if (maxChunksPerDocument <= 0) {
            throw new IllegalArgumentException("maxChunksPerDocument must be positive");
        }
    }
}
