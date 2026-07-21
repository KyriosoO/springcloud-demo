package com.dylan.agent.kernel.core;

import com.dylan.agent.invocation.model.ExecutionStage;
import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Objects;

public final class ExecutionFailure implements ExecutionOutcome {

    private final ExecutionStage stage;
    private final KernelErrorCode errorCode;
    private final String diagnosticId;
    private final boolean cancelled;
    private final String safeMessage;

    public ExecutionFailure(ExecutionStage stage,
                            KernelErrorCode errorCode,
                            String diagnosticId,
                            boolean cancelled) {
        this(stage, errorCode, diagnosticId, cancelled, null);
    }

    public ExecutionFailure(ExecutionStage stage,
                            KernelErrorCode errorCode,
                            String diagnosticId,
                            boolean cancelled,
                            String safeMessage) {
        this.stage = Objects.requireNonNull(stage);
        this.errorCode = Objects.requireNonNull(errorCode);
        this.diagnosticId = Objects.requireNonNull(diagnosticId);
        this.cancelled = cancelled;
        this.safeMessage = normalizeSafeMessage(safeMessage);
    }

    public ExecutionStage stage() { return stage; }
    public KernelErrorCode errorCode() { return errorCode; }
    public String diagnosticId() { return diagnosticId; }
    public boolean cancelled() { return cancelled; }
    public String safeMessage() { return safeMessage; }

    private static String normalizeSafeMessage(String safeMessage) {
        if (safeMessage == null || safeMessage.isBlank()) {
            return null;
        }
        return safeMessage.trim();
    }
}
