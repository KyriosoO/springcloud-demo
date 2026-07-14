package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentCoverage;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentParameters;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQuerySortParameter;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.api.response.DocumentResultCandidateSecurityEvidence;
import com.dylan.agent.api.response.DocumentResultSecurityEvidence;
import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;
import com.dylan.agent.capability.document.security.DocumentFinalDecisionDigests;
import com.dylan.agent.capability.document.security.DocumentResultCandidateSetCanonicalizer;
import com.dylan.agent.capability.document.security.DocumentSecurityReasonCode;
import com.dylan.agent.kernel.resource.DocumentCapabilityResourceLimitContract;
import com.dylan.agent.kernel.resource.DocumentResourceLimits;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.kernel.resource.ResourceLimitBindingIdentity;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentResultSecurityProjectorTest {
    private static final Instant NOW = Instant.parse("2026-07-02T00:00:01Z");

    @Test
    void supportsDocumentResultContract() {
        DocumentResultSecurityProjector projector = projector();

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.DOCUMENT_RESULT);
        assertThat(projector.payloadType()).isEqualTo(DocumentAgentResultPayload.class);
    }

    @Test
    void acceptsStableCitationSequenceAndCitationBoundText() {
        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(
                payload("政策要求如下。[C1]"), scope(), limits());

        assertThat(filtered.payload().getDocumentResult().getCitations())
                .extracting(AgentDocumentCitation::getCitationId)
                .containsExactly("C1");
        assertThat(filtered.payload().getDocumentResult().getHits().getFirst().getCitationIds())
                .containsExactly("C1");
        assertThat(filtered.safeMessage()).isEqualTo("文档结果已通过安全校验。");
    }

    @Test
    void filtersAndMasksCallerFilterValuesLocally() {
        DocumentAgentResultPayload payload = payload("政策要求如下。[C1]");
        AgentQueryFilterParameter allowed = new AgentQueryFilterParameter();
        allowed.setField("phoneNo");
        allowed.setOperator(AgentOperator.EQ);
        allowed.setValue("13812345678");
        AgentQueryFilterParameter denied = new AgentQueryFilterParameter();
        denied.setField("idCardNo");
        denied.setOperator(AgentOperator.EQ);
        denied.setValue("110101199001010011");
        payload.getDocumentParameters().setFilters(List.of(allowed, denied));

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(payload, scope(), limits());

        assertThat(filtered.payload().getDocumentParameters().getFilters())
                .singleElement()
                .satisfies(filter -> {
                    assertThat(filter.getField()).isEqualTo("phoneNo");
                    assertThat(filter.getValue()).isEqualTo("138****5678");
                });
    }

    @Test
    void projectsDocumentFieldsAndDoesNotMutateRawCandidate() {
        DocumentAgentResultPayload candidate = payload("政策要求如下。[C1]");
        AgentDocumentHit hit = candidate.getDocumentResult().getHits().getFirst();
        hit.setTitle("公开标题");
        hit.setSourceType("内部来源");
        hit.setSnippet("13812345678");
        AgentDocumentCitation citation = candidate.getDocumentResult().getCitations().getFirst();
        citation.setTitle("公开标题");
        citation.setSection("内部章节");
        citation.setSourceUri("https://internal.example/doc-1");
        citation.setSnippet("13812345678");
        AgentQuerySortParameter allowedSort = new AgentQuerySortParameter();
        allowedSort.setField("title");
        allowedSort.setDirection("ASC");
        AgentQuerySortParameter deniedSort = new AgentQuerySortParameter();
        deniedSort.setField("sourceType");
        deniedSort.setDirection("DESC");
        candidate.getDocumentParameters().setSorts(List.of(allowedSort, deniedSort));

        FilteredResult<DocumentAgentResultPayload> filtered = projector().filter(
                candidate,
                scope(Set.of("phoneNo", "title", "snippet"), Map.of(
                        "policy_document.phoneNo", MaskType.MOBILE,
                        "policy_document.snippet", MaskType.MOBILE)),
                limits());

        assertThat(filtered.payload()).isNotSameAs(candidate);
        assertThat(filtered.payload().getDocumentParameters().getSorts())
                .extracting(AgentQuerySortParameter::getField)
                .containsExactly("title");
        assertThat(filtered.payload().getDocumentResult().getHits().getFirst())
                .satisfies(projected -> {
                    assertThat(projected.getTitle()).isEqualTo("公开标题");
                    assertThat(projected.getSourceType()).isNull();
                    assertThat(projected.getSnippet()).isEqualTo("138****5678");
                });
        assertThat(filtered.payload().getDocumentResult().getCitations().getFirst())
                .satisfies(projected -> {
                    assertThat(projected.getTitle()).isEqualTo("公开标题");
                    assertThat(projected.getSection()).isNull();
                    assertThat(projected.getSourceUri()).isNull();
                    assertThat(projected.getSnippet()).isEqualTo("138****5678");
                });
        assertThat(hit.getSourceType()).isEqualTo("内部来源");
        assertThat(hit.getSnippet()).isEqualTo("13812345678");
        assertThat(candidate.getDocumentParameters().getSorts()).hasSize(2);
    }

    @Test
    void rejectsUnknownCitationMarker() {
        assertThatThrownBy(() -> projector().filter(payload("未经绑定的结论。[C2]"), scope(), limits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown citation marker");
    }

    @Test
    void rejectsCitationMarkerThatIsNotAtSentenceOrUnitBoundary() {
        assertThatThrownBy(() -> projector().filter(
                payload("结论 [C1] 仍有未绑定文本"), scope(), limits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("invalid citation position");
    }

    @Test
    void rejectsCitationDocumentIdentityThatDoesNotMatchCurrentnessCandidate() {
        DocumentAgentResultPayload payload = payload("政策要求如下。[C1]");
        payload.getDocumentResult().getCitations().getFirst().setDocumentId("doc-2");

        assertThatThrownBy(() -> projector().filter(payload, scope(), limits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("candidate ordering");
    }

    @Test
    void rejectsCoverageThatDoesNotMatchVisibleCitations() {
        DocumentAgentResultPayload payload = payload("政策要求如下。[C1]");
        payload.getDocumentResult().getCoverage().setEvidenceCount(2);

        assertThatThrownBy(() -> projector().filter(payload, scope(), limits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("coverage binding");
    }

    @Test
    void rejectsUnsafeSourceUriDuringFinalProjection() {
        DocumentAgentResultPayload payload = payload("政策要求如下。[C1]");
        payload.getDocumentResult().getCitations().getFirst().setSourceUri("javascript:alert(1)");

        assertThatThrownBy(() -> projector().filter(
                payload, scope(Set.of("sourceUri"), Map.of()), limits()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("source URI");
    }

    @Test
    void rejectsPublicPayloadWithoutCorpusBinding() {
        DocumentAgentResultPayload payload = payload("政策要求如下。[C1]");
        payload.getDocumentParameters().setMaterialType(null);

        assertThatThrownBy(() -> projector().filter(payload, scope(), limits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("corpus binding");
    }

    private static DocumentResultSecurityProjector projector() {
        return new DocumentResultSecurityProjector(
                maskingSupport(), new ObjectMapper(), Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static DocumentAgentResultPayload payload(String answerText) {
        AgentDocumentParameters parameters = new AgentDocumentParameters();
        parameters.setDomain("policy_document");
        parameters.setMaterialType("policy");
        parameters.setOperation("ANSWER");
        parameters.setQueryText("税收优惠");
        parameters.setFilters(List.of());
        parameters.setTopK(1);

        AgentDocumentCitation citation = new AgentDocumentCitation();
        citation.setCitationId("C1");
        citation.setDocumentId("doc-1");
        citation.setSnippet("政策证据");
        citation.setChunkIndex(0);

        AgentDocumentHit hit = new AgentDocumentHit();
        hit.setDocumentId("doc-1");
        hit.setSnippet("政策证据");
        hit.setScore(BigDecimal.ONE);
        hit.setCitationIds(List.of("C1"));

        AgentDocumentResult result = new AgentDocumentResult();
        result.setAnswerText(answerText);
        result.setHits(List.of(hit));
        result.setCitations(List.of(citation));
        result.setSummaryBullets(List.of());
        AgentDocumentCoverage coverage = new AgentDocumentCoverage();
        coverage.setRequestedDocumentCount(0);
        coverage.setRequestedCountKnown(false);
        coverage.setCoveredDocumentCount(1);
        coverage.setEvidenceCount(1);
        result.setCoverage(coverage);
        DocumentAgentResultPayload payload = new DocumentAgentResultPayload(parameters, result);
        payload.setInternalSecurityEvidence(securityEvidence());
        return payload;
    }

    private static DocumentResultSecurityEvidence securityEvidence() {
        String digest = "a".repeat(64);
        String limitDigest = limits().reference().canonicalDigest();
        DocumentResultCandidateSecurityEvidence candidate = new DocumentResultCandidateSecurityEvidence(
                "candidate-1", "doc-1", "v1", "chunk-1", 0,
                digest, digest, "acl-1", "acl-v1", digest, digest, digest, limitDigest);
        List<DocumentResultCandidateSecurityEvidence> candidates = List.of(candidate);
        List<String> evidenceRefs = List.of("C1");
        String candidateSetDigest = new DocumentResultCandidateSetCanonicalizer().digest(
                candidates, evidenceRefs, AgentExecutionContracts.DOCUMENT_RESULT);
        Instant validUntil = NOW.plusSeconds(2);
        String decisionDigest = DocumentFinalDecisionDigests.digest(
                DocumentCurrentnessOutcome.ALLOW, "inv-1", "op-document-1", "perm-v1",
                candidateSetDigest, limitDigest, limitDigest, "acl-decision-v1", "emergency-v1",
                NOW, validUntil, DocumentSecurityReasonCode.CURRENT);
        return new DocumentResultSecurityEvidence(
                DocumentCurrentnessOutcome.ALLOW.name(), "inv-1", "op-document-1", "perm-v1",
                candidateSetDigest, limitDigest, limitDigest, "acl-decision-v1", "emergency-v1",
                NOW, validUntil, decisionDigest, DocumentSecurityReasonCode.CURRENT.name(),
                candidates, evidenceRefs);
    }

    private static ExecutionScope scope() {
        return scope(
                Set.of("phoneNo"),
                Map.of("policy_document.phoneNo", MaskType.MOBILE));
    }

    private static ExecutionScope scope(Set<String> allowedFields, Map<String, MaskType> fieldMasks) {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog", "adapter", "availability",
                        Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer"),
                Set.of("policy_document"),
                Map.of("policy_document", allowedFields),
                fieldMasks,
                limits());
    }

    private static EffectiveCapabilityResourceLimits limits() {
        var value = DocumentResourceLimits.defaults();
        var contract = new DocumentCapabilityResourceLimitContract();
        return new EffectiveCapabilityResourceLimits(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.document.DocumentResourceLimit.class,
                value,
                contract.canonicalDigest(value),
                new ResourceLimitBindingIdentity(
                        "inv-1", "corr-1", "document.answer@v1", "a".repeat(64),
                        Instant.parse("2026-07-02T00:00:00Z")));
    }

    private static ResultValueMaskingSupport maskingSupport() {
        return new ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker())));
    }
}
