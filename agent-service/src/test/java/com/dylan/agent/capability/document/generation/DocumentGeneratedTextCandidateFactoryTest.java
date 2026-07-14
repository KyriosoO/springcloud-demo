package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationRequestBinder;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationBindingRegistry;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.agent.mask.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentGeneratedTextCandidateFactoryTest {

    @Test
    void createsTrustedCandidateFromSuccessfulBoundOutcome() {
        Fixture fixture = fixture(List.of("C1"), "回答 [C1]", true);

        DocumentGeneratedTextCandidate candidate = fixture.factory.create(
                fixture.evidencePackage, fixture.request, fixture.outcome,
                fixture.plan, fixture.context.executionScope(), fixture.context.resourceLimits());

        assertThat(candidate.securityBinding().invocationId()).isEqualTo(fixture.context.invocationId());
        assertThat(candidate.providerBinding()).isEqualTo(fixture.providerBinding);
        assertThat(candidate.citedIds()).containsExactly("C1");
        assertThatThrownBy(() -> fixture.factory.create(
                fixture.evidencePackage, fixture.request, fixture.outcome,
                fixture.plan, fixture.context.executionScope(), fixture.context.resourceLimits()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("provider binding missing");
    }

    @Test
    void rejectsUnknownCitationAndMissingTrustedProviderBinding() {
        Fixture unknownCitation = fixture(List.of("C2"), "回答 [C2]", true);
        assertThatThrownBy(() -> unknownCitation.factory.create(
                unknownCitation.evidencePackage, unknownCitation.request, unknownCitation.outcome,
                unknownCitation.plan, unknownCitation.context.executionScope(), unknownCitation.context.resourceLimits()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("citation binding");

        Fixture missingBinding = fixture(List.of("C1"), "回答 [C1]", false);
        assertThatThrownBy(() -> missingBinding.factory.create(
                missingBinding.evidencePackage, missingBinding.request, missingBinding.outcome,
                missingBinding.plan, missingBinding.context.executionScope(), missingBinding.context.resourceLimits()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("provider binding missing");
    }

    private static Fixture fixture(List<String> citedIds, String answer, boolean includeProviderBinding) {
        var requestParameters = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.ANSWER, "policy_document", "年假", true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER, "policy_document", requestParameters);
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = context.executionScope();
        Clock clock = Clock.fixed(scope.recheckedAt().plusMillis(1), ZoneOffset.UTC);
        var evidence = DocumentEvidenceTestFixtures.evidence(
                "政策", null, null, null, "年假证据", null, null,
                List.of(), List.of(), 0, null);
        var fields = new DocumentProviderIntendedFieldView(List.of(
                new com.dylan.agent.metadata.domain.port.CanonicalFieldRef("policy_document", "title"),
                new com.dylan.agent.metadata.domain.port.CanonicalFieldRef("policy_document", "snippet")));
        var decisionResult = new DocumentProviderOutboundPolicyDecisionFactory(
                new DocumentProviderOutboundPolicyCanonicalizer(), clock).create(
                CapabilityOperationType.of("DOCUMENT_GENERATION"), scope, plan.selectedCorpus(),
                plan.profile().generationPolicy(), fields, plan.profile().profileProjectionDigest(),
                context.absoluteDeadline());
        var decision = ((DocumentProviderOutboundPolicyAllowed) decisionResult).decision();
        var fieldProjector = new DocumentProviderOutboundFieldProjector(
                new com.dylan.agent.metadata.result.ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(), new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()))));
        var projection = new DocumentGenerationEvidenceProjector(fieldProjector).project(
                List.of(evidence), new DocumentEvidencePackingLimit(100, 100, 100, 5), decision,
                context.executionScope());
        var evidencePackage = new EvidenceContextPackageFactory().create(
                new EvidenceContextPackageRequest(
                        plan, context, DocumentEvidenceTestFixtures.responseBinding(evidence, plan, context), decision),
                projection);
        var input = new DocumentGenerationInputProjector().project(
                evidencePackage, DocumentGenerationInstructionCode.ANSWER_WITH_CITATIONS,
                DocumentGenerationOutputShape.ANSWER);
        var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_GENERATION"));
        var binder = new DocumentProviderOperationRequestBinder(
                new DocumentProviderCanonicalizer(new ObjectMapper()), clock);
        var operationRequest = new DocumentGenerationOperationRequest(
                input, binder.bind(decision, input, operationContext), operationContext);
        var providerBinding = new DocumentProviderBindingReference(
                operationContext.operationType(), new ProviderSafeIdentity("test-provider", Optional.empty()),
                "adapter-service", "deployment-v1", "vendor-v1", "e".repeat(64), "f".repeat(64));
        var metadata = new CapabilityOperationMetadata(
                operationContext.operationId(), operationContext.operationType(), providerBinding.provider(),
                1, 1, CapabilityOperationTermination.SUCCEEDED, "diagnostic",
                context.resourceLimits().reference(), false, false, false);
        var operationBindingRegistry = new DocumentProviderOperationBindingRegistry(clock);
        if (includeProviderBinding) {
            operationBindingRegistry.publish(
                    operationContext.operationId(), providerBinding, context.absoluteDeadline());
        }
        var payload = new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER, answer, null, List.of(), citedIds,
                DocumentProviderFinishReason.COMPLETED);
        return new Fixture(plan, context, evidencePackage, operationRequest,
                new CapabilityOperationSuccess<>(payload, metadata), providerBinding,
                new DocumentGeneratedTextCandidateFactory(binder, operationBindingRegistry));
    }

    private record Fixture(
            ValidatedDocumentPlan plan,
            com.dylan.agent.kernel.core.ExecutionContext context,
            EvidenceContextPackage evidencePackage,
            DocumentGenerationOperationRequest request,
            CapabilityOperationOutcome<DocumentUntrustedGenerationPayload> outcome,
            DocumentProviderBindingReference providerBinding,
            DocumentGeneratedTextCandidateFactory factory) {}
}
