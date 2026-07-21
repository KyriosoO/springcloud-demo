package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.response.GroundingStatus;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.assertj.core.api.Assertions.assertThat;

class DocumentCitationVerifierTest {
    private final DocumentCitationVerifier verifier = new DocumentCitationVerifier();

    @Test
    void acceptsOnlyCitationIdsFromTheExactEvidencePackage() {
        var result = payload(List.of("C1"));
        assertThat(verifier.verify(result, context()).status()).isEqualTo(GroundingStatus.VERIFIED);
        assertThat(verifier.verify(payload(List.of("C9")), context()).status()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(verifier.verify(payload(List.of()), context()).status()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(verifier.verify(new DocumentUntrustedGenerationPayload(DocumentPlanOperation.ANSWER,
                "无引用正文", null, List.of(), List.of("C1"), DocumentProviderFinishReason.COMPLETED), context()).status())
                .isEqualTo(GroundingStatus.UNVERIFIED);
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER, "回答 [C01]", null, List.of(), List.of("C01"),
                DocumentProviderFinishReason.COMPLETED)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsMarkersOutsideSentenceOrUnitBoundaryAndInsideCodeOrUri() {
        assertThat(verifier.verify(new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER, "结论 [C1] 仍有未绑定文本", null, List.of(), List.of("C1"),
                DocumentProviderFinishReason.COMPLETED), context()).status()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(verifier.verify(new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER, "`example [C1]`", null, List.of(), List.of("C1"),
                DocumentProviderFinishReason.COMPLETED), context()).status()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(verifier.verify(new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER, "https://example.test/[C1]", null, List.of(), List.of("C1"),
                DocumentProviderFinishReason.COMPLETED), context()).status()).isEqualTo(GroundingStatus.UNVERIFIED);
    }

    private static DocumentUntrustedGenerationPayload payload(List<String> ids) {
        return new DocumentUntrustedGenerationPayload(DocumentPlanOperation.ANSWER, "回答 [C1]", null,
                List.of(), ids, DocumentProviderFinishReason.COMPLETED);
    }

    private static EvidenceContextPackage context() {
        var hit = DocumentEvidenceTestFixtures.evidence(
                "政策", null, null, null, "证据", null, null, List.of(), List.of(), 0, null);
        var security = hit.securityBinding();
        var binding = new com.dylan.agent.adapter.api.document.DocumentRetrievalResponseBinding(
                security.requestCorrelationId(), "op-1", security.corpusKey(), security.targetBinding(),
                security.profileProjectionDigest(), security.resourceLimitReference(), "9".repeat(64),
                security.protectedFilterDigest(), security.aclEvidenceDigest());
        var item = new GenerationEvidencePackageItem(
                "C1", hit.candidateId(), hit.identity(), hit.title(), null, null, "证据", hit.securityBinding());
        return new EvidenceContextPackage("ECP-" + "a".repeat(24), "inv-1", "corr-1", "document.answer",
                DocumentPlanOperation.ANSWER, binding.corpusKey(), binding.profileProjectionDigest(),
                binding.resourceLimitReference(), AgentExecutionContracts.DOCUMENT_RESULT,
                binding.authorizationBindingDigest(), binding.aclEvidenceDigest(), "b".repeat(64),
                binding.protectedFilterDigest(), "c".repeat(64), List.of(item),
                new DocumentEvidenceUsage(1, 2, 4, false), "d".repeat(64));
    }
}
