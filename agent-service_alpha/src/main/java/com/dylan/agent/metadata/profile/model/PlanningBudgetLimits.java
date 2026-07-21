package com.dylan.agent.metadata.profile.model;

import java.time.Duration;
import java.util.Objects;

/** 仅由 Route/Plan/repair 消费的规划预算，不进入执行资源限额。 */
public record PlanningBudgetLimits(Duration maxTotalDuration, int maxRepairAttempts) {

    public PlanningBudgetLimits {
        Objects.requireNonNull(maxTotalDuration, "maxTotalDuration must not be null");
        if (maxTotalDuration.isZero() || maxTotalDuration.isNegative()) {
            throw new IllegalArgumentException("maxTotalDuration must be positive");
        }
        if (maxRepairAttempts < 0) {
            throw new IllegalArgumentException("maxRepairAttempts must be non-negative");
        }
    }

    public PlanningBudgetLimits intersect(PlanningBudgetLimits other) {
        Objects.requireNonNull(other, "other must not be null");
        return new PlanningBudgetLimits(
                maxTotalDuration.compareTo(other.maxTotalDuration) <= 0
                        ? maxTotalDuration : other.maxTotalDuration,
                Math.min(maxRepairAttempts, other.maxRepairAttempts));
    }
}
