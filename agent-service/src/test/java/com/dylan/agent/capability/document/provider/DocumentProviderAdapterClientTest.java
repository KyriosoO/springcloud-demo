package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.ResourceAccessException;

import java.net.SocketTimeoutException;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DocumentProviderAdapterClientTest {
    private static final CapabilityOperationType GENERATION =
            CapabilityOperationType.of("DOCUMENT_GENERATION");

    @Test
    void classifiesTransportTimeoutSeparatelyFromProviderUnavailability() {
        assertThat(DocumentProviderAdapterClient.transportFailureCode(
                new ResourceAccessException("timeout", new SocketTimeoutException("read timed out"))))
                .isEqualTo(CapabilityOperationFailureCode.PROVIDER_TIMEOUT);
        assertThat(DocumentProviderAdapterClient.transportFailureCode(
                new ResourceAccessException("connection refused")))
                .isEqualTo(CapabilityOperationFailureCode.PROVIDER_UNAVAILABLE);
    }

    @Test
    void invalidGenerationPayloadDoesNotPublishTrustedProviderBinding() throws Exception {
        var execution = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = execution.executionScope();
        Clock clock = Clock.fixed(scope.recheckedAt().plusMillis(1), ZoneOffset.UTC);
        var operationContext = execution.operationContext(GENERATION);
        ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
        var canonicalizer = new DocumentProviderCanonicalizer(mapper);
        var binding = binding(canonicalizer);
        var snapshot = snapshot(canonicalizer, binding, operationContext);
        var decision = ((DocumentProviderOutboundPolicyAllowed)
                new DocumentProviderOutboundPolicyDecisionFactory(
                        new DocumentProviderOutboundPolicyCanonicalizer(), clock).create(
                        GENERATION, scope, new DocumentCorpusKey("policy_document", "policy_document"),
                        DocumentFeaturePolicy.OPTIONAL,
                        new DocumentProviderIntendedFieldView(List.of(
                                new CanonicalFieldRef("policy_document", "title"),
                                new CanonicalFieldRef("policy_document", "snippet"))),
                        "a".repeat(64), scope.absoluteDeadline())).decision();
        var input = new DocumentGenerationInputProjection(
                "package-1", "b".repeat(64), DocumentPlanOperation.ANSWER,
                DocumentGenerationInstructionCode.ANSWER_WITH_CITATIONS,
                List.of(new DocumentGenerationEvidenceItem("C1", "title", null, null, "evidence")),
                DocumentGenerationOutputShape.ANSWER);
        var binder = new DocumentProviderOperationRequestBinder(canonicalizer, clock);
        var reference = binder.bind(decision, input, operationContext);
        var registry = new DocumentProviderOperationBindingRegistry(clock);

        RestClient.Builder builder = RestClient.builder().baseUrl("http://provider.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        String requestDigest = binder.wireRequestDigest(
                "DPW-1", operationContext, snapshot.canonicalDigest(), binding.canonicalDigest(), input);
        DocumentResourceLimit limits = operationContext.resourceLimits().require(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        var invalidPayload = new DocumentUntrustedGenerationPayload(
                DocumentPlanOperation.ANSWER,
                "x".repeat(limits.output().maxGeneratedChars() + 1), null, List.of(), List.of("C1"),
                DocumentProviderFinishReason.COMPLETED);
        var wireResponse = new DocumentProviderWireResponse<>(
                "DPW-1", operationContext.operationId(), GENERATION, requestDigest,
                snapshot.canonicalDigest(), binding, invalidPayload);
        server.expect(requestTo("http://provider.test/internal/document-providers/generation"))
                .andRespond(withSuccess(mapper.writeValueAsString(wireResponse), MediaType.APPLICATION_JSON));
        DocumentProviderAuthHeaderProvider auth = mock(DocumentProviderAuthHeaderProvider.class);
        when(auth.authorizationHeader()).thenReturn("Bearer test-token");
        var client = new DocumentProviderAdapterClient(
                builder.build(), auth, ignored -> snapshot, binder,
                new DocumentProviderOutboundPolicyReferenceVerifier(binder, clock), registry,
                clock, mapper, 2_000_000L, 2_000_000L, java.time.Duration.ofSeconds(5));

        var outcome = client.generate(new DocumentGenerationOperationRequest(
                input, reference, operationContext));

        assertThat(outcome).isInstanceOf(CapabilityOperationFailure.class);
        var failure = (CapabilityOperationFailure<DocumentUntrustedGenerationPayload>) outcome;
        assertThat(failure.code()).isEqualTo(CapabilityOperationFailureCode.INVALID_RESPONSE);
        assertThatThrownBy(() -> registry.consume(failure.metadata()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("missing or mismatched");
        server.verify();
    }

    private static DocumentProviderBindingReference binding(DocumentProviderCanonicalizer canonicalizer) {
        ProviderSafeIdentity provider = new ProviderSafeIdentity("provider-safe", Optional.of("model-safe"));
        String digest = canonicalizer.providerBindingDigest(
                GENERATION, provider, "document-provider-adapter", "deployment-1",
                "vendor-v1", "d".repeat(64));
        return new DocumentProviderBindingReference(
                GENERATION, provider, "document-provider-adapter", "deployment-1",
                "vendor-v1", "d".repeat(64), digest);
    }

    private static DocumentProviderActivationSnapshot snapshot(
            DocumentProviderCanonicalizer canonicalizer,
            DocumentProviderBindingReference binding,
            CapabilityOperationContext context) {
        String digest = canonicalizer.activationSnapshotDigest(
                GENERATION, DocumentProviderActivationState.ACTIVE, binding,
                "DPW-1", "rollout-1", context.absoluteDeadline());
        return new DocumentProviderActivationSnapshot(
                GENERATION, DocumentProviderActivationState.ACTIVE, Optional.of(binding),
                "DPW-1", "rollout-1", context.absoluteDeadline(), digest);
    }
}
