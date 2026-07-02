package com.dylan.agent.metadata.policy.model;

import java.time.Duration;
import java.util.Objects;

/** Explicit upper bounds; D02 does not treat missing limits as infinity. */
public record BudgetLimits(
        Duration maxTotalDuration,
        int maxRepairAttempts,
        int maxPageSize,
        int maxResultRows,
        long maxResultBytes) {
    public BudgetLimits {
        Objects.requireNonNull(maxTotalDuration, "maxTotalDuration must not be null");
        if (maxTotalDuration.isZero() || maxTotalDuration.isNegative()) {
            throw new IllegalArgumentException("maxTotalDuration must be positive");
        }
        if (maxRepairAttempts < 0 || maxPageSize < 0 || maxResultRows < 0 || maxResultBytes < 0) {
            throw new IllegalArgumentException("budget numeric limits must be non-negative");
        }
    }
}
