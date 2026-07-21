package com.dylan.agent.capability.document.generation;

/** 05 evidence package的本地typed上界；不进入Provider wire。 */
public record DocumentEvidencePackingLimit(
        int maxContextChars,
        int maxEvidenceChars,
        int maxSnippetChars,
        int maxEvidenceCount) {
    public DocumentEvidencePackingLimit {
        if (maxContextChars <= 0 || maxEvidenceChars <= 0
                || maxSnippetChars <= 0 || maxEvidenceCount <= 0) {
            throw new IllegalArgumentException("evidence packing limits must be positive");
        }
    }
}
