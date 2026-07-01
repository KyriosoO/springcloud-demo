package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;

import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Core 返回 Lifecycle 的内部候选结果。
 * 不包含持久化终态或 API DTO。
 */
public interface ExecutionOutcome {
    boolean isSuccess();
}

final class ExecutionSuccess {
    // unused wrapper — only ExecutionSuccess.Impl is used

    static final class Impl implements ExecutionOutcome {
        private final Object securedResult; // SecuredResult after D02_03
        private final List<Object> approvedContextWrites; // List<ApprovedContextWrite>
        private final String capabilityId;
        private final AgentPlanKind planKind;

        Impl(Object securedResult, List<Object> approvedContextWrites,
                String capabilityId, AgentPlanKind planKind) {
            this.securedResult = Objects.requireNonNull(securedResult);
            this.approvedContextWrites = List.copyOf(
                    approvedContextWrites != null ? approvedContextWrites : List.of());
            this.capabilityId = Objects.requireNonNull(capabilityId);
            this.planKind = Objects.requireNonNull(planKind);
        }

        @Override public boolean isSuccess() { return true; }

        public Object securedResult() { return securedResult; }
        public List<Object> approvedContextWrites() { return approvedContextWrites; }
        public String capabilityId() { return capabilityId; }
        public AgentPlanKind planKind() { return planKind; }
    }
}

final class ExecutionFailure {
    // unused wrapper — only ExecutionFailure.Impl is used

    static final class Impl implements ExecutionOutcome {
        private final String stage; // ExecutionStage name
        private final String errorCode; // KernelErrorCode name
        private final String diagnosticId;
        private final boolean cancelled;

        Impl(String stage, String errorCode, String diagnosticId, boolean cancelled) {
            this.stage = Objects.requireNonNull(stage);
            this.errorCode = Objects.requireNonNull(errorCode);
            this.diagnosticId = Objects.requireNonNull(diagnosticId);
            this.cancelled = cancelled;
        }

        @Override public boolean isSuccess() { return false; }

        public String stage() { return stage; }
        public String errorCode() { return errorCode; }
        public String diagnosticId() { return diagnosticId; }
        public boolean cancelled() { return cancelled; }
    }
}
