package com.dylan.agent.lifecycle.model;

import java.util.Optional;

/**
 * Planning checkpoint CAS 结果。
 *
 * <p>按 D02_02 §4.4 设计：COMMITTED 和 ALREADY_COMMITTED_SAME 时携带
 * {@link CommittedCheckpoint}；其他状态 checkpoint 参数必须为空。
 */
public final class CheckpointResult {

    private final Status status;
    private final CommittedCheckpoint committed;

    private CheckpointResult(Status status, CommittedCheckpoint committed) {
        this.status = java.util.Objects.requireNonNull(status);
        this.committed = committed;
    }

    public static CheckpointResult committed(Status status, CommittedCheckpoint committed) {
        if (status != Status.COMMITTED && status != Status.ALREADY_COMMITTED_SAME) {
            throw new IllegalArgumentException(
                    "committed() only for COMMITTED/ALREADY_COMMITTED_SAME, got " + status);
        }
        java.util.Objects.requireNonNull(committed);
        return new CheckpointResult(status, committed);
    }

    public static CheckpointResult withoutCheckpoint(Status status) {
        if (status == Status.COMMITTED || status == Status.ALREADY_COMMITTED_SAME) {
            throw new IllegalArgumentException(
                    "withoutCheckpoint() not for " + status);
        }
        return new CheckpointResult(status, null);
    }

    public Status status() { return status; }
    public Optional<CommittedCheckpoint> committed() { return Optional.ofNullable(committed); }

    public CommittedCheckpoint requireCommittedCheckpoint() {
        java.util.Objects.requireNonNull(committed, "no checkpoint for status " + status);
        return committed;
    }

    public enum Status {
        COMMITTED,
        ALREADY_COMMITTED_SAME,
        TERMINAL_EXISTS,
        ROLLBACK_CONFIRMED,
        COMMIT_UNKNOWN
    }

    /**
     * 已提交 checkpoint 的安全引用。
     */
    public record CommittedCheckpoint(
            String invocationId,
            String requestCorrelationId,
            String checkpointHash) {
        public CommittedCheckpoint {
            java.util.Objects.requireNonNull(invocationId);
            java.util.Objects.requireNonNull(requestCorrelationId);
            java.util.Objects.requireNonNull(checkpointHash);
            if (invocationId.isBlank()) {
                throw new IllegalArgumentException("invocationId must not be blank");
            }
            if (requestCorrelationId.isBlank()) {
                throw new IllegalArgumentException("requestCorrelationId must not be blank");
            }
            if (checkpointHash.isBlank()) {
                throw new IllegalArgumentException("checkpointHash must not be blank");
            }
        }
    }
}
