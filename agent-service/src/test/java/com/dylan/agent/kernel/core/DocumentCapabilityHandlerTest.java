package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityHandler;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentCapabilityHandlerTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void writesCitationIdsFromHitsWhenCitationsAreNotExplicit() {
        var result = new DocumentCapabilityHandler().execute(plan(), context());

        assertThat(result.output().getDocumentResult().getCitations()).singleElement()
                .extracting(citation -> citation.getCitationId())
                .isEqualTo("chunk-1");
        assertThat(result.contextWrites()).singleElement().satisfies(write -> {
            DocumentCapabilityContextPayload payload =
                    (DocumentCapabilityContextPayload) write.payload();
            assertThat(payload.citationIds()).containsExactly("chunk-1");
        });
    }

    private ValidatedDocumentPlan plan() {
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                "policy_document",
                "查询休假政策",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                false);
        return ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request);
    }

    private ExecutionContext context() {
        DocumentRetrievableAdapter adapter = request -> {
            AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
            evidence.setDocumentId("doc-1");
            evidence.setChunkId("chunk-1");
            evidence.setTitle("休假政策");
            evidence.setSnippet("员工年假需要直属主管审批。");
            evidence.setScore(new BigDecimal("0.92"));
            AdapterDocumentResult result = new AdapterDocumentResult();
            result.setHits(List.of(evidence));
            result.setRequestedDocumentCount(1);
            result.setCoveredDocumentCount(1);
            return result;
        };
        return new ExecutionContext(
                "inv-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                new AdapterExecutionBinding(
                        AdapterRole.DOCUMENT_RETRIEVABLE,
                        "policy_document",
                        DocumentRetrievableAdapter.class,
                        adapter,
                        "adapter-reg-test",
                        NOW),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }
}
