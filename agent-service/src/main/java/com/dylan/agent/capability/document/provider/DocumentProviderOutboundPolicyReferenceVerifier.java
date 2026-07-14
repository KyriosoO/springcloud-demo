package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderOutboundPolicyReference;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;

import java.time.Clock;
import java.util.Objects;

/** 在 adapter client 写出前复核不可重算的 trusted policy reference。 */
public final class DocumentProviderOutboundPolicyReferenceVerifier {
    private final DocumentProviderOperationRequestBinder binder;
    private final Clock clock;

    public DocumentProviderOutboundPolicyReferenceVerifier(
            DocumentProviderOperationRequestBinder binder,
            Clock clock) {
        this.binder = Objects.requireNonNull(binder, "binder must not be null");
        this.clock = Objects.requireNonNull(clock, "clock must not be null");
    }

    public boolean verify(
            DocumentProviderOutboundPolicyReference reference,
            Object input,
            CapabilityOperationContext context) {
        if (reference == null || input == null || context == null
                || !clock.instant().isBefore(reference.validUntil())) {
            return false;
        }
        return reference.invocationId().equals(context.invocationId())
                && reference.operationId().equals(context.operationId())
                && reference.operationType().equals(context.operationType())
                && reference.resourceLimitReference().equals(context.resourceLimits().reference())
                && reference.inputDigest().equals(binder.digest(input))
                && reference.validUntil().equals(context.absoluteDeadline())
                && binder.consumeMinted(reference);
    }
}
