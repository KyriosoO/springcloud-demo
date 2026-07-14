package com.dylan.agent.capability.document.profile;

/** Profile 冻结的确定性候选和 RRF 参数。 */
public record DocumentFusionPolicy(
        int keywordCandidateCount,
        int vectorCandidateCount,
        int rrfK,
        int numCandidates,
        int rerankTopN) {
    public DocumentFusionPolicy {
        if (keywordCandidateCount <= 0 || vectorCandidateCount <= 0 || rrfK <= 0
                || numCandidates <= 0 || rerankTopN <= 0) {
            throw new IllegalArgumentException("document fusion policy values must be positive");
        }
    }
}
