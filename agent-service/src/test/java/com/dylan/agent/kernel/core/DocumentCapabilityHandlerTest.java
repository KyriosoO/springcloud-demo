package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentAclScope;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.plan.DocumentGenerationFailurePolicy;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.capability.document.DocumentCapabilityHandler;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.DocumentObservabilitySupport;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.capability.document.acl.DocumentAclScopePort;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingResult;
import com.dylan.agent.capability.document.embedding.DisabledDocumentEmbeddingPort;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
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
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@ExtendWith(OutputCaptureExtension.class)
class DocumentCapabilityHandlerTest {

    private static final Instant NOW = Instant.now().plusSeconds(300);

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
        properties.getDocument().getGeneration().setModel("test-generation");
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
    void selectsTopScoreGroupBeforeGenerationAndKeepsEvidenceBudget() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        properties.getDocument().getEvidenceSelection().setStrategy(
                com.dylan.agent.config.AgentProperties.EvidenceSelectionStrategy.SCORE_GROUP_TOP);
        properties.getDocument().setMaxEvidenceCount(8);
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request(DocumentPlanOperation.ANSWER),
                options);
        AtomicReference<DocumentGenerationRequest> captured = new AtomicReference<>();
        DocumentGenerationPort generation = generationRequest -> {
            captured.set(generationRequest);
            return new DocumentGenerationResult(
                    "员工年假需要直属主管审批。[chunk-1]",
                    null,
                    null,
                    List.of(new CitationBinding("员工年假需要直属主管审批。", List.of("chunk-1"))),
                    "stop");
        };
        DocumentRetrievableAdapter adapter = request -> adapterResult(List.of(
                evidence("chunk-1", "0.99"),
                evidence("chunk-2", "0.97"),
                evidence("chunk-3", "0.96"),
                evidence("chunk-4", "0.65"),
                evidence("chunk-5", "0.63"),
                evidence("chunk-6", "0.60"),
                evidence("chunk-7", "0.58"),
                evidence("chunk-8", "0.56"),
                evidence("chunk-9", "0.54"),
                evidence("chunk-10", "0.50")));

        new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                generation,
                new DocumentCitationVerifier())
                .execute(plan, DocumentCapabilityHandlerTestSupport.context(adapter));

        assertThat(captured.get()).isNotNull();
        assertThat(captured.get().contextPackage().evidenceItems())
                .extracting(item -> item.citationId())
                .containsExactly("chunk-1", "chunk-2", "chunk-3");
        assertThat(captured.get().contextPackage().evidenceItems()).hasSizeLessThanOrEqualTo(8);
    }

    @Test
    void degradesHybridRetrievalToKeywordWhenEmbeddingProviderFails(CapturedOutput output) {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setModel("test-embedding");
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
        assertThat(output).contains("document hybrid retrieval degraded")
                .contains("invocationId=inv-1")
                .contains("domain=policy_document")
                .contains("requestedMode=HYBRID")
                .contains("effectiveMode=KEYWORD")
                .contains("reason=EMBEDDING_PROVIDER_FAILURE")
                .doesNotContain("查询休假政策")
                .doesNotContain("queryVector");
    }

    @Test
    void failsClosedWhenHybridEmbeddingDimensionMismatches() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setModel("test-embedding");
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

    @Test
    void fallsBackWhenGenerationReturnsNoCitationBindings() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        options.setFailurePolicy(DocumentGenerationFailurePolicy.FALLBACK_EXTRACTIVE);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request(DocumentPlanOperation.ANSWER),
                options);
        DocumentGenerationPort generation = request -> new DocumentGenerationResult(
                "没有引用绑定的回答。",
                null,
                null,
                List.of(),
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
                .isEqualTo(DocumentGenerationStatus.FALLBACK);
        assertThat(result.output().getDocumentResult().getCandidateAnswerText()).isNull();
        assertThat(result.output().getDocumentResult().getCitationVerification().getFallbackReason())
                .isEqualTo("NO_BINDINGS");
    }

    @Test
    void refusesWhenGenerationBindingsAreInvalidAndPolicyIsRefuse() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        options.setFailurePolicy(DocumentGenerationFailurePolicy.REFUSE);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request(DocumentPlanOperation.ANSWER),
                options);
        DocumentGenerationPort generation = request -> new DocumentGenerationResult(
                "引用不存在的回答。[missing]",
                null,
                null,
                List.of(new CitationBinding("引用不存在的回答。", List.of("missing"))),
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
                .isEqualTo(DocumentGenerationStatus.FAILED);
        assertThat(result.output().getDocumentResult().getCandidateAnswerText()).isNull();
        assertThat(result.output().getDocumentResult().getCitationVerification().getInvalidCitationIds())
                .containsExactly("missing");
    }

    @Test
    void generatesSummaryWithVerifiedCitationsAndSummaryScopeCoverage() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        DocumentSummaryScope summaryScope = new DocumentSummaryScope();
        summaryScope.setDocumentIds(List.of("doc-1", "doc-1", "doc-2"));
        summaryScope.setMaxSummaryChars(120);
        DocumentRetrievalRequest request = request(DocumentPlanOperation.SUMMARIZE);
        request = new DocumentRetrievalRequest(
                request.getOperation(),
                request.getDomain(),
                request.getQueryText(),
                request.getFilters(),
                request.getSorts(),
                request.getTopK(),
                request.getPage(),
                request.getSize(),
                summaryScope,
                true,
                request.getRetrievalMode(),
                request.getQueryVector(),
                request.getHybridOptions(),
                request.getContextOptions(),
                request.getAclScope());
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SUMMARIZE,
                "policy_document",
                request,
                options);
        DocumentGenerationPort generation = generationRequest -> {
            assertThat(generationRequest.maxOutputChars()).isEqualTo(120);
            return new DocumentGenerationResult(
                    null,
                    "生成式摘要。[chunk-1]",
                    List.of("摘要要点。[chunk-1]"),
                    List.of(new CitationBinding("生成式摘要。", List.of("chunk-1"))),
                    "stop");
        };

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
        assertThat(result.output().getDocumentResult().getCandidateSummaryText())
                .isEqualTo("生成式摘要。[chunk-1]");
        assertThat(result.output().getDocumentResult().getCoverage().getRequestedDocumentCount()).isEqualTo(2);
    }

    @Test
    void passesRequestIdModelAndDeadlineToGenerationProvider() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        DocumentGenerationOptions options = new DocumentGenerationOptions();
        options.setEnabled(true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request(DocumentPlanOperation.ANSWER),
                options);
        AtomicReference<DocumentGenerationRequest> captured = new AtomicReference<>();
        DocumentGenerationPort generation = generationRequest -> {
            captured.set(generationRequest);
            return new DocumentGenerationResult(
                    "员工年假需要直属主管审批。[chunk-1]",
                    null,
                    null,
                    List.of(new CitationBinding("员工年假需要直属主管审批。", List.of("chunk-1"))),
                    "stop");
        };

        new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                generation,
                new DocumentCitationVerifier())
                .execute(plan, context());

        assertThat(captured.get()).isNotNull();
        assertThat(captured.get().requestId()).isEqualTo("inv-1");
        assertThat(captured.get().model()).isEqualTo("test-generation");
        assertThat(captured.get().deadline()).isEqualTo(context().absoluteDeadline());
    }

    @Test
    void failsClosedWhenHybridEmbeddingModelMismatches() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setModel("expected-embedding");
        properties.getDocument().getEmbedding().setDimension(2);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request(DocumentPlanOperation.SEARCH, DocumentRetrievalMode.HYBRID));

        var handler = new DocumentCapabilityHandler(
                properties,
                request -> new DocumentEmbeddingResult(List.of(0.1, 0.2), "other-embedding", 2, "digest"),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());

        assertThatThrownBy(() -> handler.execute(plan, context()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("model mismatch");
    }

    @Test
    void failsClosedWhenHybridEmbeddingModelIsMissing() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getEmbedding().setEnabled(true);
        properties.getDocument().getEmbedding().setModel("expected-embedding");
        properties.getDocument().getEmbedding().setDimension(2);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.SEARCH,
                "policy_document",
                request(DocumentPlanOperation.SEARCH, DocumentRetrievalMode.HYBRID));

        var handler = new DocumentCapabilityHandler(
                properties,
                request -> new DocumentEmbeddingResult(List.of(0.1, 0.2), null, 2, "digest"),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());

        assertThatThrownBy(() -> handler.execute(plan, context()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("model mismatch");
    }

    @Test
    void rejectsExpiredAclScopeBeforeCallingAdapter() {
        AtomicBoolean adapterCalled = new AtomicBoolean(false);
        DocumentRetrievableAdapter adapter = request -> {
            adapterCalled.set(true);
            return adapterResult();
        };
        DocumentAclScopePort expiredAcl = request -> new DocumentAclScope(
                "tenant-1",
                "u-1",
                List.of(),
                List.of(),
                List.of(),
                "acl-expired",
                Instant.now().minusSeconds(1));

        var handler = new DocumentCapabilityHandler(
                com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties(),
                new DisabledDocumentEmbeddingPort(),
                expiredAcl,
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());

        assertThatThrownBy(() -> handler.execute(plan(), DocumentCapabilityHandlerTestSupport.context(adapter)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ACL scope is expired");
        assertThat(adapterCalled).isFalse();
    }

    @Test
    void rejectsBlocklistedDocumentDomainBeforeCallingAdapter() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setDomains(List.of("policy_document"));
        AtomicBoolean adapterCalled = new AtomicBoolean(false);
        DocumentRetrievableAdapter adapter = request -> {
            adapterCalled.set(true);
            return adapterResult();
        };

        var handler = new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier());

        assertThatThrownBy(() -> handler.execute(plan(), DocumentCapabilityHandlerTestSupport.context(adapter)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");
        assertThat(adapterCalled).isFalse();
    }

    @Test
    void recordsRetrievalAndGenerationProviderMetrics() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getGeneration().setEnabled(true);
        properties.getDocument().getGeneration().setModel("test-generation");
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
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

        new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentRevocationGuard(properties),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                generation,
                new DocumentCitationVerifier(),
                new DocumentObservabilitySupport(registry))
                .execute(plan, context());

        assertThat(registry.counter(
                "agent_document_retrieval_total",
                "domain", "policy_document",
                "mode", "KEYWORD",
                "result", "SUCCESS").count()).isEqualTo(1.0);
        assertThat(registry.counter(
                "agent_document_provider_total",
                "providerType", "generation",
                "operation", "ANSWER",
                "result", "SUCCESS").count()).isEqualTo(1.0);
    }

    @Test
    void recordsRevocationMetricBeforeRejectingBlocklistedDomain() {
        var properties = com.dylan.agent.testsupport.DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setDomains(List.of("policy_document"));
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        AtomicBoolean adapterCalled = new AtomicBoolean(false);
        DocumentRetrievableAdapter adapter = request -> {
            adapterCalled.set(true);
            return adapterResult();
        };

        var handler = new DocumentCapabilityHandler(
                properties,
                new DisabledDocumentEmbeddingPort(),
                aclScopePort(),
                new DocumentRevocationGuard(properties),
                new DocumentEvidencePreSecurityFilter(),
                new DocumentEvidenceContextPacker(),
                new DisabledDocumentGenerationPort(),
                new DocumentCitationVerifier(),
                new DocumentObservabilitySupport(registry));

        assertThatThrownBy(() -> handler.execute(plan(), DocumentCapabilityHandlerTestSupport.context(adapter)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");
        assertThat(adapterCalled).isFalse();
        assertThat(registry.counter(
                "agent_document_revocation_hit_total",
                "target", "DOMAIN",
                "source", "LOCAL_BLOCKLIST").count()).isEqualTo(1.0);
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
        return adapterResult(List.of(evidence("chunk-1", "0.92")));
    }

    private AdapterDocumentResult adapterResult(List<AdapterDocumentEvidence> evidence) {
        AdapterDocumentResult result = new AdapterDocumentResult();
        result.setHits(evidence);
        result.setRequestedDocumentCount(evidence.size());
        result.setCoveredDocumentCount((int) evidence.stream()
                .map(AdapterDocumentEvidence::getDocumentId)
                .distinct()
                .count());
        return result;
    }

    private AdapterDocumentEvidence evidence(String chunkId, String score) {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-" + chunkId);
        evidence.setChunkId(chunkId);
        evidence.setTitle("休假政策");
        evidence.setSnippet("员工年假需要直属主管审批。");
        evidence.setScore(new BigDecimal(score));
        return evidence;
    }
}
