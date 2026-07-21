package com.dylan.agent.adapter.api.document;

/** 同 target/filter 的批量 context window 约束。 */
public record DocumentContextSpec(int beforeChunks, int afterChunks, int maxContextChars) {
    public DocumentContextSpec {
        if (beforeChunks < 0 || afterChunks < 0 || maxContextChars < 0) {
            throw new IllegalArgumentException("document context spec invalid");
        }
    }
}
