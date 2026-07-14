package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import java.util.Objects;

/** DLRL-1：文档能力的完整 typed ResourceLimit。 */
public record DocumentResourceLimit(
        DocumentInputLimit input,
        DocumentRetrievalLimit retrieval,
        DocumentEnhancementLimit enhancement,
        DocumentEvidenceOutputLimit output) implements CapabilityResourceLimit {

    public DocumentResourceLimit {
        Objects.requireNonNull(input, "input must not be null");
        Objects.requireNonNull(retrieval, "retrieval must not be null");
        Objects.requireNonNull(enhancement, "enhancement must not be null");
        Objects.requireNonNull(output, "output must not be null");
    }

    public DocumentResourceLimit stricterOf(DocumentResourceLimit other) {
        Objects.requireNonNull(other, "other must not be null");
        return new DocumentResourceLimit(
                input.stricterOf(other.input),
                retrieval.stricterOf(other.retrieval),
                enhancement.stricterOf(other.enhancement),
                output.stricterOf(other.output));
    }

    public record DocumentInputLimit(int maxQueryChars, int maxCallerFilterCount) {
        public DocumentInputLimit { positive(maxQueryChars, "maxQueryChars"); nonNegative(maxCallerFilterCount, "maxCallerFilterCount"); }
        DocumentInputLimit stricterOf(DocumentInputLimit other) { return new DocumentInputLimit(Math.min(maxQueryChars, other.maxQueryChars), Math.min(maxCallerFilterCount, other.maxCallerFilterCount)); }
    }

    public record DocumentRetrievalLimit(
            int maxChannelCount,
            int maxCandidatesPerChannel,
            int maxFusedCandidates,
            int maxChunksPerDocument,
            int maxReturnedDocuments) {
        public DocumentRetrievalLimit {
            positive(maxChannelCount, "maxChannelCount"); positive(maxCandidatesPerChannel, "maxCandidatesPerChannel");
            positive(maxFusedCandidates, "maxFusedCandidates"); positive(maxChunksPerDocument, "maxChunksPerDocument");
            positive(maxReturnedDocuments, "maxReturnedDocuments");
        }
        DocumentRetrievalLimit stricterOf(DocumentRetrievalLimit other) {
            return new DocumentRetrievalLimit(Math.min(maxChannelCount, other.maxChannelCount), Math.min(maxCandidatesPerChannel, other.maxCandidatesPerChannel), Math.min(maxFusedCandidates, other.maxFusedCandidates), Math.min(maxChunksPerDocument, other.maxChunksPerDocument), Math.min(maxReturnedDocuments, other.maxReturnedDocuments));
        }
    }

    public record DocumentEnhancementLimit(
            int maxRewriteCandidates,
            int maxEmbeddingTexts,
            int maxEmbeddingDimensions,
            int maxRerankCandidates) {
        public DocumentEnhancementLimit {
            nonNegative(maxRewriteCandidates, "maxRewriteCandidates"); nonNegative(maxEmbeddingTexts, "maxEmbeddingTexts");
            nonNegative(maxEmbeddingDimensions, "maxEmbeddingDimensions"); nonNegative(maxRerankCandidates, "maxRerankCandidates");
        }
        DocumentEnhancementLimit stricterOf(DocumentEnhancementLimit other) {
            return new DocumentEnhancementLimit(Math.min(maxRewriteCandidates, other.maxRewriteCandidates), Math.min(maxEmbeddingTexts, other.maxEmbeddingTexts), Math.min(maxEmbeddingDimensions, other.maxEmbeddingDimensions), Math.min(maxRerankCandidates, other.maxRerankCandidates));
        }
    }

    public record DocumentEvidenceOutputLimit(
            int maxEvidenceCount,
            int maxEvidenceChars,
            int maxSnippetChars,
            int maxContextChars,
            int maxCitationCount,
            int maxGeneratedChars,
            int maxSummaryChars,
            int maxSummaryBullets,
            long maxResultBytes) {
        public DocumentEvidenceOutputLimit {
            positive(maxEvidenceCount, "maxEvidenceCount"); positive(maxEvidenceChars, "maxEvidenceChars");
            positive(maxSnippetChars, "maxSnippetChars"); nonNegative(maxContextChars, "maxContextChars");
            nonNegative(maxCitationCount, "maxCitationCount"); nonNegative(maxGeneratedChars, "maxGeneratedChars");
            nonNegative(maxSummaryChars, "maxSummaryChars"); nonNegative(maxSummaryBullets, "maxSummaryBullets");
            if (maxResultBytes <= 0) throw new IllegalArgumentException("maxResultBytes must be positive");
        }
        DocumentEvidenceOutputLimit stricterOf(DocumentEvidenceOutputLimit other) {
            return new DocumentEvidenceOutputLimit(Math.min(maxEvidenceCount, other.maxEvidenceCount), Math.min(maxEvidenceChars, other.maxEvidenceChars), Math.min(maxSnippetChars, other.maxSnippetChars), Math.min(maxContextChars, other.maxContextChars), Math.min(maxCitationCount, other.maxCitationCount), Math.min(maxGeneratedChars, other.maxGeneratedChars), Math.min(maxSummaryChars, other.maxSummaryChars), Math.min(maxSummaryBullets, other.maxSummaryBullets), Math.min(maxResultBytes, other.maxResultBytes));
        }
    }

    private static void positive(int value, String name) { if (value <= 0) throw new IllegalArgumentException(name + " must be positive"); }
    private static void nonNegative(int value, String name) { if (value < 0) throw new IllegalArgumentException(name + " must not be negative"); }
}
