package com.dylan.agent.adapter.api.document.provider;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProviderContractValidationTest {

    @Test
    void rejectsDuplicateRerankIdsAndInvalidEmbeddingValues() {
        var item = new DocumentRerankInputProjection.DocumentRerankInputItem("candidate-1", "title", "snippet");
        assertThatThrownBy(() -> new DocumentRerankInputProjection("query", List.of(item, item)))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("duplicates");
        assertThatThrownBy(() -> new DocumentUntrustedEmbeddingPayload(
                List.of(List.of(1.0f, Float.NaN)), 2,
                new com.dylan.agent.adapter.api.document.DocumentEmbeddingBindingReference(
                        "a".repeat(64), 2)))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("vector");
    }

    @Test
    void rejectsGenerationUnionAndCitationAliases() {
        var evidence = new DocumentGenerationEvidenceItem("C1", "title", null, 1, "evidence");
        assertThatThrownBy(() -> new DocumentGenerationInputProjection(
                "package-1", "a".repeat(64), DocumentPlanOperation.ANSWER,
                DocumentGenerationInstructionCode.SUMMARIZE_WITH_CITATIONS,
                List.of(evidence), DocumentGenerationOutputShape.ANSWER))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("union");
        assertThatThrownBy(() -> new DocumentGenerationEvidenceItem(
                "citation:1", null, null, null, "evidence"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("canonical");
    }

    @Test
    void rejectsUnknownOrIncompleteWireBindingsAtConstructionBoundary() {
        assertThatThrownBy(() -> new DocumentProviderWireError(
                "DPW-1", "operation-1", com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_RERANK"),
                "not-a-digest", DocumentProviderAdapterFailureCode.VENDOR_FAILED, "diagnostic-1"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("requestDigest");
    }
}
