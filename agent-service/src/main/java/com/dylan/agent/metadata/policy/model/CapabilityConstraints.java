package com.dylan.agent.metadata.policy.model;

import java.util.Objects;
import java.util.Optional;

/** capability 级 deployment switch 和可选 budget tightening。 */
public record CapabilityConstraints(
        boolean enabled,
        Optional<BudgetLimits> budgetLimits) {
    public CapabilityConstraints {
        budgetLimits = Objects.requireNonNull(budgetLimits, "budgetLimits must not be null");
    }
}
