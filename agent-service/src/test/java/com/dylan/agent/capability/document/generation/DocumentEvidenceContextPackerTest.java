package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidenceContextPackerTest {

    @Test
    void packsOnlyFilteredEvidenceWithinBudget() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("c-1");
        evidence.setContent("员工年假需要直属主管审批。");
        evidence.setContextBefore(List.of("员工申请年假前需要提交申请。"));
        evidence.setContextAfter(List.of("审批通过后由人事归档。"));
        evidence.setRrfScore(new BigDecimal("0.03"));
        var request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "年假审批",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var packed = new DocumentEvidenceContextPacker().pack(new DocumentContextPackRequest(
                plan,
                List.of(evidence),
                DocumentCapabilityHandlerTestSupport.context(adapterRequest -> null),
                new DocumentContextBudget(100, 50, 5, 100)));

        assertThat(packed.citationIds()).containsExactly("c-1");
        assertThat(packed.evidenceItems()).singleElement()
                .extracting(DocumentEvidenceContextItem::text)
                .isEqualTo("员工申请年假前需要提交申请。\n员工年假需要直属主管审批。\n审批通过后由人事归档。");
        assertThat(packed.digest()).isNotBlank();
    }
}
