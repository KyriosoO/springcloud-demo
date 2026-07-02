package com.dylan.agent.metadata.policy.model;

import java.util.Objects;
import java.util.Optional;

/** Capability-level deployment switch and optional budget tightening. */
public record CapabilityConstraints(
        boolean enabled,
        Optional<BudgetLimits> budgetLimits) {
    public CapabilityConstraints {
        budgetLimits = Objects.requireNonNull(budgetLimits, "budgetLimits must not be null");
    }
}
