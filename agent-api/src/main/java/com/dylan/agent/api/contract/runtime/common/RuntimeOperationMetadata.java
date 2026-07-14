package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.Objects;

/**
 * Route/Plan 双阶段的统一操作遥测。
 *
 * <p>providerAttempts 是所有 provider 调用的总数；repairAttempts 不得大于
 * {@code max(providerAttempts - 1, 0)}。
 */
@Schema(description = "Runtime 操作元数据")
public class RuntimeOperationMetadata {

    @Schema(description = "操作类型", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private RuntimeOperationType operation;

    @Schema(description = "provider 调用总数", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    private Integer providerAttempts;

    @Schema(description = "repair 调用次数", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    private Integer repairAttempts;

    @Schema(description = "repair 累计耗时 (ms)", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    private Long repairDurationMs;

    @Schema(description = "操作总耗时 (ms)", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Min(0)
    private Long totalDurationMs;

    @Schema(description = "终止原因", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private RuntimeTerminationReason terminationReason;

    @Schema(description = "deadline 是否已到期", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private Boolean deadlineReached;

    @Schema(description = "是否达到 repair 上限", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private Boolean repairLimitReached;

    public RuntimeOperationMetadata() {
    }

    // ── getters / setters ──

    public RuntimeOperationType getOperation() { return operation; }
    public void setOperation(RuntimeOperationType operation) { this.operation = operation; }
    public Integer getProviderAttempts() { return providerAttempts; }
    public void setProviderAttempts(Integer providerAttempts) { this.providerAttempts = providerAttempts; }
    public Integer getRepairAttempts() { return repairAttempts; }
    public void setRepairAttempts(Integer repairAttempts) { this.repairAttempts = repairAttempts; }
    public Long getRepairDurationMs() { return repairDurationMs; }
    public void setRepairDurationMs(Long repairDurationMs) { this.repairDurationMs = repairDurationMs; }
    public Long getTotalDurationMs() { return totalDurationMs; }
    public void setTotalDurationMs(Long totalDurationMs) { this.totalDurationMs = totalDurationMs; }
    public RuntimeTerminationReason getTerminationReason() { return terminationReason; }
    public void setTerminationReason(RuntimeTerminationReason terminationReason) { this.terminationReason = terminationReason; }
    public Boolean getDeadlineReached() { return deadlineReached; }
    public void setDeadlineReached(Boolean deadlineReached) { this.deadlineReached = deadlineReached; }
    public Boolean getRepairLimitReached() { return repairLimitReached; }
    public void setRepairLimitReached(Boolean repairLimitReached) { this.repairLimitReached = repairLimitReached; }

    /** 在 HTTP/Planning 信任边界校验无法由字段注解表达的组合不变量。 */
    public void validateFor(RuntimeOperationType expectedOperation) {
        Objects.requireNonNull(expectedOperation, "expectedOperation must not be null");
        if (operation != expectedOperation) {
            throw new IllegalArgumentException("runtime metadata operation mismatch");
        }
        if (providerAttempts == null || providerAttempts < 0) {
            throw new IllegalArgumentException("providerAttempts must be non-negative");
        }
        if (repairAttempts == null || repairAttempts < 0
                || repairAttempts > Math.max(providerAttempts - 1, 0)) {
            throw new IllegalArgumentException("repairAttempts exceeds providerAttempts");
        }
        if (repairDurationMs == null || repairDurationMs < 0
                || totalDurationMs == null || totalDurationMs < 0) {
            throw new IllegalArgumentException("runtime durations must be non-negative");
        }
        Objects.requireNonNull(terminationReason, "terminationReason must not be null");
        Objects.requireNonNull(deadlineReached, "deadlineReached must not be null");
        Objects.requireNonNull(repairLimitReached, "repairLimitReached must not be null");
    }
}
