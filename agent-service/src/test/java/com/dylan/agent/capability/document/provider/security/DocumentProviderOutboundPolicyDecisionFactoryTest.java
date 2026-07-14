package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentProviderOutboundPolicyDecisionFactoryTest {

    @Test
    void createsDeterministicAllowedDecisionFromCurrentExecutionScope() {
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = context.executionScope();
        var factory = factory(scope.recheckedAt().plusMillis(1));
        var type = CapabilityOperationType.of("DOCUMENT_GENERATION");
        var fields = new DocumentProviderIntendedFieldView(List.of(
                new CanonicalFieldRef("policy_document", "title"),
                new CanonicalFieldRef("policy_document", "snippet")));

        var first = factory.create(type, scope,
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey("policy_document", "policy_document"),
                DocumentFeaturePolicy.OPTIONAL, fields, "a".repeat(64), scope.absoluteDeadline());
        var second = factory.create(type, scope,
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey("policy_document", "policy_document"),
                DocumentFeaturePolicy.OPTIONAL, fields, "a".repeat(64), scope.absoluteDeadline());

        assertThat(first).isInstanceOf(DocumentProviderOutboundPolicyAllowed.class);
        assertThat(((DocumentProviderOutboundPolicyAllowed) first).decision().canonicalDigest())
                .isEqualTo(((DocumentProviderOutboundPolicyAllowed) second).decision().canonicalDigest());
    }

    @Test
    void deniesTheWholeOperationWhenAnyFieldHasNoPurposeRule() {
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = context.executionScope();
        var result = factory(scope.recheckedAt().plusMillis(1)).create(
                CapabilityOperationType.of("DOCUMENT_GENERATION"), scope,
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey("policy_document", "policy_document"),
                DocumentFeaturePolicy.OPTIONAL,
                new DocumentProviderIntendedFieldView(List.of(
                        new CanonicalFieldRef("policy_document", "sourceUri"))),
                "a".repeat(64), scope.absoluteDeadline());

        assertThat(result).isEqualTo(new DocumentProviderOutboundPolicyDenied(
                DocumentProviderOutboundPolicyDenialCode.CLASSIFICATION_PURPOSE_NOT_ALLOWED));
    }

    @Test
    void deniesDisabledFeatureBeforeProviderInvocation() {
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        var scope = context.executionScope();
        var result = factory(scope.recheckedAt().plusMillis(1)).create(
                CapabilityOperationType.of("DOCUMENT_REWRITE"), scope,
                new com.dylan.agent.adapter.api.document.DocumentCorpusKey("policy_document", "policy_document"),
                DocumentFeaturePolicy.DISABLED, DocumentProviderIntendedFieldView.queryOnly(),
                "a".repeat(64), scope.absoluteDeadline());

        assertThat(result).isEqualTo(new DocumentProviderOutboundPolicyDenied(
                DocumentProviderOutboundPolicyDenialCode.FEATURE_DISABLED));
    }

    private static DocumentProviderOutboundPolicyDecisionFactory factory(java.time.Instant now) {
        return new DocumentProviderOutboundPolicyDecisionFactory(
                new DocumentProviderOutboundPolicyCanonicalizer(),
                Clock.fixed(now, ZoneOffset.UTC));
    }
}
