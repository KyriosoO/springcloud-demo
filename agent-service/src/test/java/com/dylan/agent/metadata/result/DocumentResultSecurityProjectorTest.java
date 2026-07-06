package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
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
                .extracting(AgentDocumentCitation::getSnippet)
                .isEqualTo("员工年假需要直属主管审批。");
        assertThat(result.getCoverage().getEvidenceCount()).isEqualTo(1);
    }

    private DocumentResultSecurityProjector projector() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        return new DocumentResultSecurityProjector(maskingSupport(), properties);
    }

    private DocumentAgentResultPayload payload() {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain("policy_document");
        parameters.setOperation("ANSWER");
        parameters.setQueryText("年假审批要求");
        parameters.setTopK(5);

        AgentDocumentCitation citation = new AgentDocumentCitation();
        citation.setCitationId("c-1");
        citation.setDocumentId("doc-1");
        citation.setTitle("休假政策");
        citation.setSnippet("员工年假需要直属主管审批。");
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
