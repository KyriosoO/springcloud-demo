package com.dylan.agent.planning.model;

import java.util.Objects;

/**
 * D01 Runtime metadata 的 Planning 侧安全审计值，由 D02_00 唯一负责。
 *
 * <p>{@code REPORTED} 时携带从 D01 {@code RuntimeOperationMetadata} 投影的安全摘要；
 * {@code NOT_REPORTED} 只用于 provider 不可达等缺失场景，不把 transport failure
 * 的零值伪造为 {@code REPORTED}。</p>
 */
public final class PlanningOperationAudit {

    private final Status status;
    private final int providerAttempts;
    private final int repairAttempts;
    private final long repairDurationMs;
    private final long totalDurationMs;
    private final String terminationReason;
    private final boolean deadlineReached;
    private final boolean repairLimitReached;

    private PlanningOperationAudit(
            Status status, int providerAttempts, int repairAttempts,
            long repairDurationMs, long totalDurationMs,
            String terminationReason, boolean deadlineReached, boolean repairLimitReached) {
        this.status = Objects.requireNonNull(status);
        this.providerAttempts = providerAttempts;
        this.repairAttempts = repairAttempts;
        this.repairDurationMs = repairDurationMs;
        this.totalDurationMs = totalDurationMs;
        this.terminationReason = Objects.requireNonNull(terminationReason);
        this.deadlineReached = deadlineReached;
        this.repairLimitReached = repairLimitReached;
    }

    public static PlanningOperationAudit reported(
            int providerAttempts, int repairAttempts,
            long repairDurationMs, long totalDurationMs,
            String terminationReason, boolean deadlineReached, boolean repairLimitReached) {
        return new PlanningOperationAudit(Status.REPORTED,
                providerAttempts, repairAttempts, repairDurationMs, totalDurationMs,
                terminationReason, deadlineReached, repairLimitReached);
    }

    public static PlanningOperationAudit notReported() {
        return new PlanningOperationAudit(Status.NOT_REPORTED, 0, 0, 0, 0, "UNKNOWN", false, false);
    }

    public Status status() { return status; }
    public int providerAttempts() { return providerAttempts; }
    public int repairAttempts() { return repairAttempts; }
    public long repairDurationMs() { return repairDurationMs; }
    public long totalDurationMs() { return totalDurationMs; }
    public String terminationReason() { return terminationReason; }
    public boolean deadlineReached() { return deadlineReached; }
    public boolean repairLimitReached() { return repairLimitReached; }

    public enum Status { REPORTED, NOT_REPORTED }
}
