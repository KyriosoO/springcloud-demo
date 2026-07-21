package com.dylan.agent.client;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.PlanningStage;

import java.util.List;
import java.util.Objects;

/**
 * 将 Runtime Route/Plan 调用失败映射为 Planning 失败事实。
 */
public final class AgentRuntimeErrorMapper {

    public PlanningFailure map(RuntimeOperationException exception, InvocationHandle handle) {
        return map(exception, handle, null);
    }

    public PlanningFailure map(
            RuntimeOperationException exception,
            InvocationHandle handle,
            PlanningOperationAudit routeAudit) {
        Objects.requireNonNull(exception, "exception must not be null");
        Objects.requireNonNull(handle, "handle must not be null");
        return new PlanningFailure(
                handle.requestCorrelationId(),
                stage(exception.operation()),
                errorCode(exception.failure()),
                exception.diagnosticId(),
                null,
                null,
                audits(exception, routeAudit));
    }

    private static PlanningStage stage(RuntimeOperationType operation) {
        return switch (operation) {
            case ROUTE -> PlanningStage.ROUTE;
            case PLAN -> PlanningStage.PLAN;
        };
    }

    private static KernelErrorCode errorCode(RuntimeOperationFailure failure) {
        return switch (failure) {
            case PROTOCOL -> KernelErrorCode.RUNTIME_CONTRACT_INVALID;
            case AUTHENTICATION -> KernelErrorCode.RUNTIME_AUTHENTICATION_FAILED;
            case DEADLINE -> KernelErrorCode.DEADLINE_EXCEEDED;
            case PROVIDER, TRANSPORT, INTERNAL -> KernelErrorCode.RUNTIME_UNAVAILABLE;
            case REPAIR_EXHAUSTED -> KernelErrorCode.RUNTIME_OUTPUT_INVALID;
        };
    }

    private static List<PlanningOperationAudit> audits(
            RuntimeOperationException exception,
            PlanningOperationAudit routeAudit) {
        if (exception.operation() == RuntimeOperationType.ROUTE) {
            return List.of(exception.audit());
        }
        if (routeAudit != null) {
            return List.of(routeAudit, exception.audit());
        }
        return List.of(
                PlanningOperationAudit.notReported(
                        RuntimeOperationType.ROUTE,
                        0L,
                        PlanningOperationTermination.CANCELLED),
                exception.audit());
    }
}
