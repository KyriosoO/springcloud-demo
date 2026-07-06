package com.dylan.agent.adapter.api.document;

/** 文档混合检索参数。 */
public final class DocumentHybridOptions {
    private final int keywordK;
    private final int vectorK;
    private final int rrfK;
    private final int numCandidates;

    public DocumentHybridOptions(int keywordK, int vectorK, int rrfK, int numCandidates) {
        this.keywordK = keywordK;
        this.vectorK = vectorK;
        this.rrfK = rrfK;
        this.numCandidates = numCandidates;
    }

    public int keywordK() { return keywordK; }
    public int vectorK() { return vectorK; }
    public int rrfK() { return rrfK; }
    public int numCandidates() { return numCandidates; }
}
