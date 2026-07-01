package com.dylan.agent.kernel.core;

import com.dylan.agent.invocation.model.ExecutionStage;
import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Objects;

public final class ExecutionFailure implements ExecutionOutcome {

    private final ExecutionStage stage;
    private final KernelErrorCode errorCode;
    private final String diagnosticId;
    private final boolean cancelled;

    public ExecutionFailure(ExecutionStage stage,
                            KernelErrorCode errorCode,
                            String diagnosticId,
                            boolean cancelled) {
        this.stage = Objects.requireNonNull(stage);
        this.errorCode = Objects.requireNonNull(errorCode);
        this.diagnosticId = Objects.requireNonNull(diagnosticId);
        this.cancelled = cancelled;
    }

    public ExecutionStage stage() { return stage; }
    public KernelErrorCode errorCode() { return errorCode; }
    public String diagnosticId() { return diagnosticId; }
    public boolean cancelled() { return cancelled; }
}
