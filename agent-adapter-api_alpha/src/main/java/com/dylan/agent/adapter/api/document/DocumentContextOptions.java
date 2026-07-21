package com.dylan.agent.adapter.api.document;

/** 文档证据上下文窗口参数。 */
public final class DocumentContextOptions {
    private final int beforeChunks;
    private final int afterChunks;
    private final int maxContextChars;

    public DocumentContextOptions(int beforeChunks, int afterChunks, int maxContextChars) {
        this.beforeChunks = beforeChunks;
        this.afterChunks = afterChunks;
        this.maxContextChars = maxContextChars;
    }

    public int beforeChunks() { return beforeChunks; }
    public int afterChunks() { return afterChunks; }
    public int maxContextChars() { return maxContextChars; }
}
