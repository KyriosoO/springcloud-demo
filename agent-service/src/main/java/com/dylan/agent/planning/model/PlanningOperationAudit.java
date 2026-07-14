package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;

import java.util.Objects;
import java.util.Optional;

/**
 * D01 Runtime metadata 的 Planning 侧安全审计值，由 D02_00 唯一负责。
 *
 * <p>{@code REPORTED} 时携带从 D01 {@code RuntimeOperationMetadata} 投影的安全摘要；
 * {@code NOT_REPORTED} 只用于 provider 不可达等缺失场景，不把 transport failure
 * 的零值伪造为 {@code REPORTED}。</p>
 */
public final class PlanningOperationAudit {

    private final RuntimeOperationType operation;
    private final RuntimeMetadataStatus metadataStatus;
    private final RuntimeOperationMetadata runtimeMetadata;
    private final long localDurationMs;
    private final PlanningOperationTermination termination;

    private PlanningOperationAudit(
            RuntimeOperationType operation,
            RuntimeMetadataStatus metadataStatus,
            RuntimeOperationMetadata runtimeMetadata,
            long localDurationMs,
            PlanningOperationTermination termination) {
        this.operation = Objects.requireNonNull(operation);
        this.metadataStatus = Objects.requireNonNull(metadataStatus);
        this.runtimeMetadata = runtimeMetadata;
        if (localDurationMs < 0) {
            throw new IllegalArgumentException("localDurationMs must be non-negative");
        }
        this.localDurationMs = localDurationMs;
        this.termination = Objects.requireNonNull(termination);

        if (metadataStatus == RuntimeMetadataStatus.REPORTED) {
            Objects.requireNonNull(runtimeMetadata, "reported audit requires runtimeMetadata");
            if (termination != PlanningOperationTermination.OUTCOME_RECEIVED
                    && termination != PlanningOperationTermination.RUNTIME_ERROR_RECEIVED) {
                throw new IllegalArgumentException("reported audit termination is invalid: " + termination);
            }
            runtimeMetadata.validateFor(operation);
        } else {
            if (runtimeMetadata != null) {
                throw new IllegalArgumentException("not reported audit must not carry runtimeMetadata");
            }
            if (termination == PlanningOperationTermination.OUTCOME_RECEIVED
                    || termination == PlanningOperationTermination.RUNTIME_ERROR_RECEIVED) {
                throw new IllegalArgumentException("not reported audit termination is invalid: " + termination);
            }
        }
    }

    public static PlanningOperationAudit reported(
            RuntimeOperationMetadata runtimeMetadata,
            long localDurationMs,
            PlanningOperationTermination termination) {
        Objects.requireNonNull(runtimeMetadata, "runtimeMetadata must not be null");
        return new PlanningOperationAudit(runtimeMetadata.getOperation(),
                RuntimeMetadataStatus.REPORTED,
                runtimeMetadata,
                localDurationMs,
                termination);
    }

    public static PlanningOperationAudit notReported(
            RuntimeOperationType operation,
            long localDurationMs,
            PlanningOperationTermination termination) {
        return new PlanningOperationAudit(operation,
                RuntimeMetadataStatus.NOT_REPORTED,
                null,
                localDurationMs,
                termination);
    }

    public RuntimeOperationType operation() { return operation; }
    public RuntimeMetadataStatus metadataStatus() { return metadataStatus; }
    public Optional<RuntimeOperationMetadata> runtimeMetadata() { return Optional.ofNullable(runtimeMetadata); }
    public long localDurationMs() { return localDurationMs; }
    public PlanningOperationTermination termination() { return termination; }
}
