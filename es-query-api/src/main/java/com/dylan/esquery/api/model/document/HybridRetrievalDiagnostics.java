package com.dylan.esquery.api.model.document;

/** 低基数、可复核的检索 diagnostics。 */
public record HybridRetrievalDiagnostics(
        int rawCandidateCount,
        int fusedCandidateCount,
        int returnedChunkCount,
        int returnedDocumentCount,
        boolean candidateTruncated,
        boolean contextTruncated) {
    public HybridRetrievalDiagnostics {
        if(rawCandidateCount<0||fusedCandidateCount<0||returnedChunkCount<0||returnedDocumentCount<0)throw new IllegalArgumentException("diagnostics count invalid");
        if(fusedCandidateCount>rawCandidateCount||returnedDocumentCount>returnedChunkCount)throw new IllegalArgumentException("diagnostics count inconsistent");
    }
}
