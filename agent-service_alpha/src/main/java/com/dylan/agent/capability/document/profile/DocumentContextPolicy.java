package com.dylan.agent.capability.document.profile;

/** 同 target/filter 批量扩展相邻 chunk 的封闭策略。 */
public record DocumentContextPolicy(int beforeChunks, int afterChunks) {
    public DocumentContextPolicy {
        if (beforeChunks < 0 || afterChunks < 0) {
            throw new IllegalArgumentException("document context chunks must not be negative");
        }
    }
}
