package com.dylan.agent.planning;

import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;

import java.util.Objects;

/**
 * 将已校验 Route 决策解析为冻结 Registration。
 */
public final class CapabilitySelectionResolver {

    private final CapabilityRegistry capabilityRegistry;

    public CapabilitySelectionResolver(CapabilityRegistry capabilityRegistry) {
        this.capabilityRegistry = Objects.requireNonNull(capabilityRegistry);
    }

    public ResolvedRegistration resolve(
            ValidatedRouteDecision decision,
            AvailableCapabilitySnapshot available) {
        Objects.requireNonNull(decision, "decision must not be null");
        Objects.requireNonNull(available, "available must not be null");
        if (!available.contains(decision.capability().capabilityId())) {
            throw new IllegalArgumentException("capability is not available");
        }
        ResolvedRegistration resolved = capabilityRegistry.resolve(decision.capability().capabilityId());
        if (resolved.planKind() != decision.capability().planKind()) {
            throw new IllegalArgumentException("resolved registration planKind mismatch");
        }
        if (!resolved.registrationIdentity().equals(decision.capability().registrationIdentity())) {
            throw new IllegalArgumentException("resolved registration identity mismatch");
        }
        return resolved;
    }
}
