package com.dylan.agent.capability.document.generation;

/** ECP 实际使用量，所有字符按 Unicode code point 计数。 */
public record DocumentEvidenceUsage(int itemCount, int evidenceChars, int contextChars, boolean truncated) {
    public DocumentEvidenceUsage {
        if (itemCount < 0 || evidenceChars < 0 || contextChars < 0) {
            throw new IllegalArgumentException("document evidence usage invalid");
        }
    }
}
