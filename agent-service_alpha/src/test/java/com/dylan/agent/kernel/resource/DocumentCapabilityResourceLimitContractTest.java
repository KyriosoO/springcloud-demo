package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentCapabilityResourceLimitContractTest {

    @Test
    void operationIntrinsicLimitsCloseGenerationAndSummaryDimensions() {
        DocumentResourceLimit search = DocumentResourceLimits.intrinsicFor("document.search");
        DocumentResourceLimit answer = DocumentResourceLimits.intrinsicFor("document.answer");
        DocumentResourceLimit summarize = DocumentResourceLimits.intrinsicFor("document.summarize");

        assertThat(search.output().maxContextChars()).isZero();
        assertThat(search.output().maxGeneratedChars()).isZero();
        assertThat(search.output().maxSummaryChars()).isZero();
        assertThat(search.output().maxSummaryBullets()).isZero();
        assertThat(answer.output().maxGeneratedChars()).isPositive();
        assertThat(answer.output().maxSummaryChars()).isZero();
        assertThat(summarize.output().maxSummaryChars()).isPositive();
    }

    private final DocumentCapabilityResourceLimitContract contract =
            new DocumentCapabilityResourceLimitContract();

    @Test
    void exposesTheCompleteStableDimensionSet() {
        assertThat(contract.supportedDimensions())
                .extracting(ResourceLimitDimension::value)
                .containsExactlyInAnyOrder(
                        "document.input.query-chars", "document.input.caller-filter-count",
                        "document.retrieval.channel-count", "document.retrieval.candidates-per-channel",
                        "document.retrieval.fused-candidates", "document.retrieval.chunks-per-document",
                        "document.retrieval.returned-documents", "document.enhancement.rewrite-candidates",
                        "document.enhancement.embedding-texts", "document.enhancement.embedding-dimensions",
                        "document.enhancement.rerank-candidates", "document.output.evidence-count",
                        "document.output.evidence-chars", "document.output.snippet-chars",
                        "document.output.context-chars", "document.output.citation-count",
                        "document.output.generated-chars", "document.output.summary-chars",
                        "document.output.summary-bullets", "document.output.result-bytes");
    }

    @Test
    void computesTheDlrl1LengthPrefixedCanonicalDigest() {
        assertThat(contract.canonicalDigest(valuesOneThroughTwenty()))
                .isEqualTo("3d81b2bad0dd458fd65ad13d1365c5d8e645a7bd5feb0266a1fb5a4b7b10256b");
    }

    @Test
    void intersectsEveryDimensionWithTheStricterValueAndAllowsZeroOptionalBudgets() {
        DocumentResourceLimit baseline = valuesOneThroughTwenty();
        DocumentResourceLimit zeroOptional = new DocumentResourceLimit(
                new DocumentResourceLimit.DocumentInputLimit(1, 0),
                new DocumentResourceLimit.DocumentRetrievalLimit(1, 1, 1, 1, 1),
                new DocumentResourceLimit.DocumentEnhancementLimit(0, 0, 0, 0),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(1, 1, 1, 0, 0, 0, 0, 0, 1L));

        DocumentResourceLimit effective = contract.intersect(baseline, zeroOptional);

        assertThat(effective).isEqualTo(zeroOptional);
        assertThat(contract.isSameOrStricter(effective, baseline)).isTrue();
    }

    private static DocumentResourceLimit valuesOneThroughTwenty() {
        return new DocumentResourceLimit(
                new DocumentResourceLimit.DocumentInputLimit(1, 2),
                new DocumentResourceLimit.DocumentRetrievalLimit(3, 4, 5, 6, 7),
                new DocumentResourceLimit.DocumentEnhancementLimit(8, 9, 10, 11),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(
                        12, 13, 14, 15, 16, 17, 18, 19, 20L));
    }
}
