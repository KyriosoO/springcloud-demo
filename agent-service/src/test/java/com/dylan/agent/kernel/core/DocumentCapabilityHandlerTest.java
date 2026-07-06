package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentAclScope;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.capability.document.DocumentCapabilityHandler;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.capability.document.acl.DocumentAclScopePort;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingResult;
import com.dylan.agent.capability.document.embedding.DisabledDocumentEmbeddingPort;
import com.dylan.agent.capability.document.generation.CitationBinding;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentEvidenceContextPacker;
import com.dylan.agent.capability.document.generation.DocumentEvidencePreSecurityFilter;
import com.dylan.agent.capability.document.generation.DisabledDocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DocumentGenerationResult;
import com.dylan.agent.capability.document.generation.DocumentGenerationRequest;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentCapabilityHandlerTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");

    @Test
    void writesCitationIdsFromHitsWhenCitationsAreNotExplicit() {
        var result = handler().execute(plan(), context());

        assertThat(result.output().getDocumentResult().getCitations()).singleElement()
                .extracting(citation -> citation.getCitationId())
                .isEqualTo("chunk-1");
        assertThat(result.contextWrites()).singleElement().satisfies(write -> {
            DocumentCapabilityContextPayload payload =
                    (DocumentCapabilityContextPayload) write.payload();
            assertThat(payload.citationIds()).containsExactly("chunk-1");
        });
    }

    @Test
    void generatesAnswerAfterHybridRetrievalWhenEnabled() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request(DocumentPlanOperation.ANSWER),
                options);
        DocumentGenerationPort generation = request -> new DocumentGenerationResult(
                "员工年假需要直属主管审批。[chunk-1]",
                null,
                null,
                List.of(new CitationBinding("员工年假需要直属主管审批。", List.of("chunk-1"))),
                "stop");

        var result = new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                generation,
                new DocumentCitationVerifier())
                .execute(plan, context());

        assertThat(result.output().getDocumentResult().getGenerationStatus())
                .isEqualTo(DocumentGenerationStatus.SUCCEEDED);
        assertThat(result.output().getDocumentResult().getCandidateAnswerText())
                .contains("员工年假需要直属主管审批");
    }

    @Test
    void degradesHybridRetrievalToKeywordWhenEmbeddingProviderFails() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setDimension(2);
        AtomicReference<DocumentRetrievalRequest> capturedRequest = new AtomicReference<>();
        DocumentRetrievableAdapter adapter = request -> {
            capturedRequest.set(request);
            return adapterResult();
        };
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request(DocumentPlanOperation.SEARCH, DocumentRetrievalMode.HYBRID));

        new DocumentCapabilityHandler(
                properties,
                request -> { throw new IllegalStateException("embedding timeout"); },
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier())
                .execute(plan, DocumentCapabilityHandlerTestSupport.context(adapter));

        assertThat(capturedRequest.get()).isNotNull();
        assertThat(capturedRequest.get().getRetrievalMode()).isEqualTo(DocumentRetrievalMode.KEYWORD);
        assertThat(capturedRequest.get().getQueryVector()).isEmpty();
    }

    @Test
    void failsClosedWhenHybridEmbeddingDimensionMismatches() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setDimension(2);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request(DocumentPlanOperation.SEARCH, DocumentRetrievalMode.HYBRID));

        var handler = new DocumentCapabilityHandler(
                properties,
                request -> new DocumentEmbeddingResult(List.of(0.1), "test-embedding", 1, "digest"),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());

        assertThatThrownBy(() -> handler.execute(plan, context()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("dimension mismatch");
    }

    private ValidatedDocumentPlan plan() {
        return ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request(DocumentPlanOperation.SEARCH));
    }

    private DocumentCapabilityHandler handler() {
        return new DocumentCapabilityHandler(
                com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties(),
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());
    }

    private DocumentAclScopePort aclScopePort() {
        return request -> new DocumentAclScope(
                "tenant-1",
                "u-1",
                List.of("dept-1"),
                List.of("role-1"),
                List.of("region:CN"),
                "acl-v1",
                Instant.now().plusSeconds(300));
    }

    private DocumentRetrievalRequest request(DocumentPlanOperation operation) {
        return request(operation, DocumentRetrievalMode.KEYWORD);
    }

    private DocumentRetrievalRequest request(DocumentPlanOperation operation, DocumentRetrievalMode retrievalMode) {
        return new DocumentRetrievalRequest(
                operation,
                "policy_document",
                "查询休假政策",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                operation != DocumentPlanOperation.SEARCH,
                retrievalMode,
                List.of(),
                null,
                null);
    }

    private ExecutionContext context() {
        DocumentRetrievableAdapter adapter = request -> adapterResult();
        return new ExecutionContext(
                "inv-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                DocumentCapabilityHandlerTestSupport.executionScope(),
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

    private AdapterDocumentResult adapterResult() {
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
    }
}
