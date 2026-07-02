package com.dylan.agent.metadata.authorization.model;

/**
 * Planning 冻结后供 Execution 消费的执行预算。
 */
public record ExecutionBudget(
        int maxRepairAttempts,
        int maxResultRows,
        long maxResultBytes) {

    public static ExecutionBudget zero() {
        return new ExecutionBudget(0, 0, 0L);
    }

    public ExecutionBudget {
        if (maxRepairAttempts < 0) {
            throw new IllegalArgumentException("maxRepairAttempts must be non-negative");
        }
        if (maxResultRows < 0) {
            throw new IllegalArgumentException("maxResultRows must be non-negative");
        }
        if (maxResultBytes < 0) {
            throw new IllegalArgumentException("maxResultBytes must be non-negative");
        }
    }
}
