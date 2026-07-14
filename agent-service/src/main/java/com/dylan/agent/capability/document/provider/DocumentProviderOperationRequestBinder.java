package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderOutboundPolicyReference;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundPolicyDecision;
import com.fasterxml.jackson.databind.ObjectMapper;

/** 绑定本 Invocation 的最小外发策略引用；正文不会进入 wire envelope。 */
public final class DocumentProviderOperationRequestBinder {
    private final DocumentProviderCanonicalizer canonicalizer;
    private final java.time.Clock clock;
    private final java.util.concurrent.ConcurrentMap<String, DocumentProviderOutboundPolicyReference> minted =
            new java.util.concurrent.ConcurrentHashMap<>();

    public DocumentProviderOperationRequestBinder(ObjectMapper objectMapper) {
        this(new DocumentProviderCanonicalizer(objectMapper), java.time.Clock.systemUTC());
    }

    public DocumentProviderOperationRequestBinder(DocumentProviderCanonicalizer canonicalizer) {
        this(canonicalizer, java.time.Clock.systemUTC());
    }

    public DocumentProviderOperationRequestBinder(
            DocumentProviderCanonicalizer canonicalizer,
            java.time.Clock clock) {
        this.canonicalizer = java.util.Objects.requireNonNull(canonicalizer);
        this.clock = java.util.Objects.requireNonNull(clock);
    }

    public DocumentProviderOutboundPolicyReference bind(
            DocumentProviderOutboundPolicyDecision decision,
            Object input,
            CapabilityOperationContext context) {
        java.util.Objects.requireNonNull(decision, "decision must not be null");
        java.util.Objects.requireNonNull(context, "context must not be null");
        if (!decision.operationType().equals(context.operationType())
                || !decision.resourceLimitReference().equals(context.resourceLimits().reference())
                || !decision.validUntil().equals(context.absoluteDeadline())) {
            throw new IllegalArgumentException("document provider decision binding mismatch");
        }
        String inputDigest = digest(input);
        DocumentProviderOutboundPolicyReference reference = new DocumentProviderOutboundPolicyReference(
                context.invocationId(), context.operationId(), context.operationType(), decision.canonicalDigest(), inputDigest,
                context.resourceLimits().reference(), context.absoluteDeadline());
        minted.entrySet().removeIf(entry -> !entry.getValue().validUntil().isAfter(clock.instant()));
        if (minted.putIfAbsent(context.operationId(), reference) != null) {
            throw new IllegalStateException("document provider operation reference already minted");
        }
        return reference;
    }

    public String digest(Object input) {
        return canonicalizer.inputDigest(java.util.Objects.requireNonNull(input, "input must not be null"));
    }

    boolean consumeMinted(DocumentProviderOutboundPolicyReference reference) {
        return reference != null && minted.remove(reference.operationId(), reference);
    }

    public String wireRequestDigest(String version, CapabilityOperationContext context,
                                    String activationDigest, String providerBindingDigest, Object input) {
        return canonicalizer.wireRequestDigest(version, context.operationId(), context.operationType(),
                context.absoluteDeadline().toEpochMilli(), activationDigest, providerBindingDigest, input);
    }
}
