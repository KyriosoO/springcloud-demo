package com.dylan.agent.metadata.authorization.model;

import java.util.Objects;
import java.util.Set;

/** Static delegation constraint; single-agent CHAT normally uses the all-scope instance. */
public record DelegationConstraint(
        DelegationConstraintRef ref,
        Set<String> allowedCapabilityIds,
        Set<String> allowedDomains) {
    public DelegationConstraint {
        Objects.requireNonNull(ref, "ref must not be null");
        allowedCapabilityIds = Set.copyOf(Objects.requireNonNull(allowedCapabilityIds, "allowedCapabilityIds must not be null"));
        allowedDomains = Set.copyOf(Objects.requireNonNull(allowedDomains, "allowedDomains must not be null"));
    }
}
