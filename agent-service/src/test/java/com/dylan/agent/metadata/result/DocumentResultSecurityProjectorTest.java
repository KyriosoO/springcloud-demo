package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentGenerationStatus;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.api.response.GroundingStatus;
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
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

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

    private DocumentResultSecurityProjector projector() {
        return projector(DomainMetadataTestSupport.agentProperties());
    }

    private DocumentResultSecurityProjector projector(AgentProperties properties) {
        return new DocumentResultSecurityProjector(maskingSupport(), properties);
    }

    private DocumentAgentResultPayload payload() {
        return payload("ANSWER");
    }

    private DocumentAgentResultPayload payload(String operation) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain("policy_document");
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
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer"),
                Set.of("policy_document"),
                Map.of("policy_document", Set.of("sourceType")),
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
