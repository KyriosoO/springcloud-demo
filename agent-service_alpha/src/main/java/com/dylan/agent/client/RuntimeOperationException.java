package com.dylan.agent.client;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.planning.model.PlanningOperationAudit;

import java.util.Objects;

/**
 * Route/Plan Runtime 调用失败。
 *
 * <p>异常只携带强类型失败事实、操作名和安全审计摘要，不包含 prompt、provider 原文、
 * JWT、权限正文或 Runtime 响应体。</p>
 */
public final class RuntimeOperationException extends RuntimeException {

    private final RuntimeOperationType operation;
    private final RuntimeOperationFailure failure;
    private final PlanningOperationAudit audit;
    private final String diagnosticId;

    public RuntimeOperationException(
            RuntimeOperationType operation,
            RuntimeOperationFailure failure,
            PlanningOperationAudit audit,
            String diagnosticId,
            Throwable cause) {
        super("Runtime operation failed: " + operation + "/" + failure, cause);
        this.operation = Objects.requireNonNull(operation, "operation must not be null");
        this.failure = Objects.requireNonNull(failure, "failure must not be null");
        this.audit = Objects.requireNonNull(audit, "audit must not be null");
        this.diagnosticId = requireNonBlank(diagnosticId, "diagnosticId");
    }

    public RuntimeOperationType operation() {
        return operation;
    }

    public RuntimeOperationFailure failure() {
        return failure;
    }

    public PlanningOperationAudit audit() {
        return audit;
    }

    public String diagnosticId() {
        return diagnosticId;
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
