package com.dylan.agent.capability.document.evidence;

public record DocumentCoverageDraft(
        int requestedDocumentCount,
        boolean requestedCountKnown,
        int coveredDocumentCount,
        int evidenceCount,
        boolean truncated) {
}
