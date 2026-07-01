package com.dylan.agent.lifecycle.model;

import com.dylan.agent.invocation.model.InvocationOrigin;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Optional;

/**
 * Lifecycle finalization 提交后返回的不可变内部结果。
 */
public final class FinalizedInvocationResult {

    private final String invocationId;
    private final InvocationOrigin origin;
    private final InvocationState state;
    private final InvocationResponseType responseType;
    private final Optional<StoredInvocationResult> storedResult;
    private final String safeMessage;
    private final Optional<KernelErrorCode> errorCode;
    private final Optional<String> diagnosticId;

    private FinalizedInvocationResult(Builder builder) {
        this.invocationId = java.util.Objects.requireNonNull(builder.invocationId);
        this.origin = java.util.Objects.requireNonNull(builder.origin);
        this.state = java.util.Objects.requireNonNull(builder.state);
        this.responseType = builder.responseType;
        this.storedResult = Optional.ofNullable(builder.storedResult);
        this.safeMessage = java.util.Objects.requireNonNull(builder.safeMessage);
        this.errorCode = Optional.ofNullable(builder.errorCode);
        this.diagnosticId = Optional.ofNullable(builder.diagnosticId);
    }

    public String invocationId() { return invocationId; }
    public InvocationOrigin origin() { return origin; }
    public InvocationState state() { return state; }
    public InvocationResponseType responseType() { return responseType; }
    public Optional<StoredInvocationResult> storedResult() { return storedResult; }
    public String safeMessage() { return safeMessage; }
    public Optional<KernelErrorCode> errorCode() { return errorCode; }
    public Optional<String> diagnosticId() { return diagnosticId; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String invocationId;
        private InvocationOrigin origin;
        private InvocationState state;
        private InvocationResponseType responseType;
        private StoredInvocationResult storedResult;
        private String safeMessage;
        private KernelErrorCode errorCode;
        private String diagnosticId;

        public Builder invocationId(String v) { this.invocationId = v; return this; }
        public Builder origin(InvocationOrigin v) { this.origin = v; return this; }
        public Builder state(InvocationState v) { this.state = v; return this; }
        public Builder responseType(InvocationResponseType v) { this.responseType = v; return this; }
        public Builder storedResult(StoredInvocationResult v) { this.storedResult = v; return this; }
        public Builder safeMessage(String v) { this.safeMessage = v; return this; }
        public Builder errorCode(KernelErrorCode v) { this.errorCode = v; return this; }
        public Builder diagnosticId(String v) { this.diagnosticId = v; return this; }
        public FinalizedInvocationResult build() {
            java.util.Objects.requireNonNull(responseType, "responseType required");
            return new FinalizedInvocationResult(this);
        }
    }
}
