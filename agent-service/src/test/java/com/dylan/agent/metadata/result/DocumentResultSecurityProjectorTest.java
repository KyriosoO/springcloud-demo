package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.api.response.GroundingStatus;
import com.dylan.agent.capability.document.DocumentObservabilitySupport;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentResultSecurityProjectorTest {

    @Test
    void supportsDocumentResultContract() {
        DocumentResultSecurityProjector projector = projector();

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.DOCUMENT_RESULT);
        assertThat(projector.payloadType()).isEqualTo(DocumentAgentResultPayload.class);
    }

    @Test
    void composesAnswerFromFilteredCitations() {
        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload(), scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getAnswerText()).contains("[c-1] 员工年假需要直属主管审批。");
        assertThat(result.getCitations()).singleElement()
                .satisfies(citation -> {
                    assertThat(citation.getSnippet()).isEqualTo("员工年假需要直属主管审批。");
                    assertThat(citation.getChunkIndex()).isEqualTo(3);
                    assertThat(citation.getCharStart()).isEqualTo(10);
                    assertThat(citation.getCharEnd()).isEqualTo(32);
                });
        assertThat(result.getCoverage().getEvidenceCount()).isEqualTo(1);
    }

    @Test
    void filtersUnauthorizedDocumentEvidenceFields() {
        DocumentAgentResultPayload payload = payload("SEARCH");
        com.dylan.agent.api.response.AgentDocumentHit hit =
                new com.dylan.agent.api.response.AgentDocumentHit();
        hit.setDocumentId("doc-1");
        hit.setTitle("休假政策");
        hit.setSourceType("policy");
        hit.setSnippet("员工年假需要直属主管审批。");
        hit.setCitationIds(List.of("c-1"));
        payload.getDocumentResult().setHits(List.of(hit));

        FilteredResult<DocumentAgentResultPayload> filtered =
                projector().filter(payload, scope(Set.of("sourceType")));

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getHits()).singleElement().satisfies(value -> {
            assertThat(value.getDocumentId()).isEqualTo("doc-1");
            assertThat(value.getSourceType()).isEqualTo("policy");
            assertThat(value.getTitle()).isNull();
            assertThat(value.getSnippet()).isNull();
        });
        assertThat(result.getCitations()).isEmpty();
        assertThat(result.getAnswerText()).isNull();
    }

    @Test
    void usesVerifiedGeneratedCandidateAndClearsCandidateFields() {
        DocumentAgentResultPayload payload = payload();
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateAnswerText("生成式回答。[c-1]");

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getAnswerText()).isEqualTo("生成式回答。[c-1]");
        assertThat(result.getCandidateAnswerText()).isNull();
    }

    @Test
    void normalizesCitationIdLabelBeforeValidatingGeneratedCandidate() {
        DocumentAgentResultPayload payload = payload();
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateAnswerText("生成式回答。[citationId:c-1]");

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getAnswerText()).isEqualTo("生成式回答。[c-1]");
        assertThat(result.getGenerationStatus()).isEqualTo(DocumentGenerationStatus.SUCCEEDED);
    }

    @Test
    void generatedTextUsesGenerationOutputBudgetNotSnippetBudget() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().setMaxSnippetChars(6);
        properties.getDocument().getGeneration().setMaxOutputChars(60);
        DocumentAgentResultPayload payload = payload("SUMMARIZE");
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateSummaryText("生成式摘要内容应允许超过片段截断长度。[c-1]");
        payload.getDocumentResult().setCandidateSummaryBullets(List.of("生成式摘要要点同样不应被片段预算截断。[c-1]"));

        FilteredResult<DocumentAgentResultPayload> filtered = projector(properties).filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getSummaryText()).isEqualTo("生成式摘要内容应允许超过片段截断长度。[c-1]");
        assertThat(result.getSummaryBullets()).containsExactly("生成式摘要要点同样不应被片段预算截断。[c-1]");
        assertThat(result.getCitations()).singleElement()
                .extracting(AgentDocumentCitation::getSnippet)
                .isEqualTo("员工年假需要");
    }

    @Test
    void fallsBackWhenSummaryBulletHasNoCitation() {
        DocumentAgentResultPayload payload = payload("SUMMARIZE");
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateSummaryText("生成式摘要正文包含引用。[c-1]");
        payload.getDocumentResult().setCandidateSummaryBullets(List.of("这条要点没有引用"));

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getGenerationStatus()).isEqualTo(DocumentGenerationStatus.FALLBACK);
        assertThat(result.getGroundingStatus()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(result.getSummaryText()).contains("[c-1] 员工年假需要直属主管审批。");
        assertThat(result.getSummaryBullets()).containsExactly("[c-1] 员工年假需要直属主管审批。");
    }

    @Test
    void fallsBackWhenSummaryReferencesFilteredCitation() {
        DocumentAgentResultPayload payload = payload("SUMMARIZE");
        AgentDocumentCitation hidden = new AgentDocumentCitation();
        hidden.setCitationId("c-2");
        hidden.setDocumentId("doc-2");
        hidden.setTitle("隐藏政策");
        hidden.setSnippet("这条证据会被结果数量限制过滤。");
        payload.getDocumentResult().setCitations(List.of(payload.getDocumentResult().getCitations().get(0), hidden));
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateSummaryText("生成式摘要只引用被过滤证据。[c-2]");
        payload.getDocumentResult().setCandidateSummaryBullets(List.of("生成式摘要要点。[c-2]"));
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(2);
        coverage.setCoveredDocumentCount(2);
        coverage.setEvidenceCount(2);
        payload.getDocumentResult().setCoverage(coverage);
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().setMaxEvidenceCount(1);

        FilteredResult<DocumentAgentResultPayload> filtered = projector(properties).filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getGenerationStatus()).isEqualTo(DocumentGenerationStatus.FALLBACK);
        assertThat(result.getSummaryText()).contains("[c-1]");
        assertThat(result.getSummaryText()).doesNotContain("[c-2]");
        assertThat(result.getCoverage().getRequestedDocumentCount()).isEqualTo(2);
        assertThat(result.getCoverage().getCoveredDocumentCount()).isEqualTo(1);
        assertThat(result.getCoverage().getEvidenceCount()).isEqualTo(1);
        assertThat(result.getCoverage().isTruncated()).isTrue();
        assertThat(result.getCandidateSummaryText()).isNull();
    }

    @Test
    void fallsBackWhenGeneratedCandidateReferencesMissingCitation() {
        DocumentAgentResultPayload payload = payload();
        payload.getDocumentResult().setGenerationStatus(DocumentGenerationStatus.SUCCEEDED);
        payload.getDocumentResult().setGroundingStatus(GroundingStatus.VERIFIED);
        payload.getDocumentResult().setCandidateAnswerText("生成式回答。[c-2]");

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload, scope());

        AgentDocumentResult result = filtered.payload().getDocumentResult();
        assertThat(result.getGenerationStatus()).isEqualTo(DocumentGenerationStatus.FALLBACK);
        assertThat(result.getGroundingStatus()).isEqualTo(GroundingStatus.UNVERIFIED);
        assertThat(result.getAnswerText()).contains("[c-1] 员工年假需要直属主管审批。");
        assertThat(result.getAnswerText()).doesNotContain("[c-2]");
        assertThat(result.getCandidateAnswerText()).isNull();
    }

    @Test
    void candidateFieldsAreNotSerializedAsPublicResult() throws Exception {
        AgentDocumentResult result = new AgentDocumentResult();
        result.setAnswerText("可见回答。[c-1]");
        result.setCandidateAnswerText("候选回答不应外露。");
        result.setCandidateSummaryText("候选摘要不应外露。");
        result.setCandidateSummaryBullets(List.of("候选要点不应外露。"));

        String json = new ObjectMapper().writeValueAsString(result);

        assertThat(json).contains("answerText");
        assertThat(json).doesNotContain("candidateAnswerText", "candidateSummaryText", "candidateSummaryBullets");
    }

    @Test
    void rejectsDomainOutsideExecutionScope() {
        DocumentAgentResultPayload payload = payload();
        payload.getDocumentParameters().setDomain("knowledge_base");

        assertThatThrownBy(() -> projector().filter(payload, scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("outside execution scope");
    }

    @Test
    void rejectsBlocklistedDomainBeforeProjectingResult() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setDomains(List.of("policy_document"));

        assertThatThrownBy(() -> projector(properties).filter(payload(), scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");
    }

    @Test
    void recordsResultSecurityDecisionMetric() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        DocumentResultSecurityProjector projector = projector(
                DomainMetadataTestSupport.agentProperties(),
                new DocumentObservabilitySupport(registry));

        projector.filter(payload(), scope());

        assertThat(registry.counter(
                "agent_document_result_security_total",
                "decision", "FILTERED").count()).isEqualTo(1.0);
    }

    @Test
    void recordsRevocationAndFailedResultSecurityMetric() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setDomains(List.of("policy_document"));
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        DocumentResultSecurityProjector projector = projector(
                properties,
                new DocumentObservabilitySupport(registry));

        assertThatThrownBy(() -> projector.filter(payload(), scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");

        assertThat(registry.counter(
                "agent_document_revocation_hit_total",
                "target", "DOMAIN",
                "source", "LOCAL_BLOCKLIST").count()).isEqualTo(1.0);
        assertThat(registry.counter(
                "agent_document_result_security_total",
                "decision", "FAILED").count()).isEqualTo(1.0);
    }

    @Test
    void rejectsRevokedRetrievalProfileDuringFinalProjection() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setRetrievalProfiles(List.of("tax-v2"));
        DocumentResultSecurityProjector projector = projector(properties);

        assertThatThrownBy(() -> projector.filter(payload(), scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");
    }

    private DocumentResultSecurityProjector projector() {
        return projector(DomainMetadataTestSupport.agentProperties());
    }

    private DocumentResultSecurityProjector projector(AgentProperties properties) {
        return new DocumentResultSecurityProjector(maskingSupport(), properties);
    }

    private DocumentResultSecurityProjector projector(
            AgentProperties properties,
            DocumentObservabilitySupport observabilitySupport) {
        return new DocumentResultSecurityProjector(
                maskingSupport(),
                properties,
                new DocumentRevocationGuard(properties),
                observabilitySupport);
    }

    private DocumentAgentResultPayload payload() {
        return payload("ANSWER");
    }

    private DocumentAgentResultPayload payload(String operation) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain("policy_document");
        parameters.setMaterialType("tax_policy");
        parameters.setRetrievalProfile("tax-v2");
        parameters.setProfileVersion("v2");
        parameters.setIndexAlias("agent-doc-tax-policy-read");
        parameters.setOperation(operation);
        parameters.setQueryText("年假审批要求");
        parameters.setTopK(5);

        AgentDocumentCitation citation = new AgentDocumentCitation();
        citation.setCitationId("c-1");
        citation.setDocumentId("doc-1");
        citation.setTitle("休假政策");
        citation.setSnippet("员工年假需要直属主管审批。");
        citation.setChunkIndex(3);
        citation.setCharStart(10);
        citation.setCharEnd(32);
        AgentDocumentResult result = new AgentDocumentResult();
        result.setCitations(List.of(citation));
        return new DocumentAgentResultPayload(parameters, result);
    }

    private ExecutionScope scope() {
        return scope(Set.of("title", "sourceType", "section", "page", "sourceUri", "snippet"));
    }

    private ExecutionScope scope(Set<String> allowedFields) {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer"),
                Set.of("policy_document"),
                Map.of("policy_document", allowedFields),
                Map.of(),
                Duration.ofSeconds(30),
                0,
                100,
                10_000);
    }

    private ResultValueMaskingSupport maskingSupport() {
        return new ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker())));
    }
}
