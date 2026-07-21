package com.dylan.agent.adapter.api.document;

/** 确定性 RRF 参数。 */
public record DocumentFusionSpec(int rrfK, int maxFusedCandidates) {
    public DocumentFusionSpec {
        if (rrfK <= 0 || maxFusedCandidates <= 0) throw new IllegalArgumentException("document fusion spec invalid");
    }
}
