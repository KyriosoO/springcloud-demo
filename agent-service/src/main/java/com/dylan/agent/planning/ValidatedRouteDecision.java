package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.metadata.catalog.AvailableCapability;

import java.util.Objects;
import java.util.Optional;

public record ValidatedRouteDecision(
        RouteDecision decision,
        AvailableCapability capability,
        Optional<String> domain) {
    public ValidatedRouteDecision {
        Objects.requireNonNull(decision, "decision must not be null");
        Objects.requireNonNull(capability, "capability must not be null");
        domain = Objects.requireNonNull(domain, "domain must not be null");
    }
}
