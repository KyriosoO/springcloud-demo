package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.response.GroundingStatus;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentCitationVerifierTest {

    @Test
    void removesUnsupportedClaimsWithoutValidCitation() {
        EvidenceContextPackage context = new EvidenceContextPackage(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "年假审批",
                List.of(new DocumentEvidenceContextItem("c-1", "员工年假需要直属主管审批。", java.util.Map.of())),
                Set.of("c-1"),
                new DocumentContextBudget(100, 50, 5, 100),
                "digest");
        DocumentGenerationResult result = new DocumentGenerationResult(
                "回答",
                null,
                null,
                List.of(new CitationBinding("回答", List.of("missing-citation"))),
                "stop");

        var verified = new DocumentCitationVerifier().verify(result, context);

        assertThat(verified.status()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(verified.invalidCitationIds()).containsExactly("missing-citation");
    }
}
