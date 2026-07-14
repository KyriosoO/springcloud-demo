package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderOutboundPolicyReference;
import com.dylan.agent.adapter.api.document.provider.DocumentRewriteInputProjection;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentProviderOutboundPolicyReferenceVerifierTest {

    @Test
    void rejectsTamperedReferenceAndConsumesValidReferenceOnce() {
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = context.executionScope();
        Clock clock = Clock.fixed(scope.recheckedAt().plusMillis(1), ZoneOffset.UTC);
        var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_REWRITE"));
        var decisionResult = new DocumentProviderOutboundPolicyDecisionFactory(
                new DocumentProviderOutboundPolicyCanonicalizer(), clock).create(
                operationContext.operationType(), scope,
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey("policy_document", "policy_document"),
                DocumentFeaturePolicy.OPTIONAL, DocumentProviderIntendedFieldView.queryOnly(),
                "a".repeat(64), scope.absoluteDeadline());
        var decision = ((DocumentProviderOutboundPolicyAllowed) decisionResult).decision();
        var binder = new DocumentProviderOperationRequestBinder(
                new DocumentProviderCanonicalizer(new ObjectMapper()), clock);
        var verifier = new DocumentProviderOutboundPolicyReferenceVerifier(binder, clock);
        var input = new DocumentRewriteInputProjection("年假", "zh-CN", 2);
        var reference = binder.bind(decision, input, operationContext);
        var tampered = new DocumentProviderOutboundPolicyReference(
                reference.invocationId(), reference.operationId(), reference.operationType(),
                "f".repeat(64), reference.inputDigest(), reference.resourceLimitReference(), reference.validUntil());

        assertThat(verifier.verify(tampered, input, operationContext)).isFalse();
        assertThat(verifier.verify(reference, input, operationContext)).isTrue();
        assertThat(verifier.verify(reference, input, operationContext)).isFalse();
    }
}
