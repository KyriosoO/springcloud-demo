package com.dylan.agent.client;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.planning.model.PlanningStage;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class AgentRuntimeErrorMapperTest {

    private static final Instant DEADLINE = Instant.parse("2026-07-02T10:00:30Z");

    private final AgentRuntimeErrorMapper mapper = new AgentRuntimeErrorMapper();

    @Test
    void mapsRouteTransportFailureToRoutePlanningFailure() {
        RuntimeOperationException exception = exception(
                RuntimeOperationType.ROUTE,
                RuntimeOperationFailure.TRANSPORT,
                PlanningOperationTermination.TRANSPORT_FAILURE);

        var failure = mapper.map(exception, handle());

        assertThat(failure.requestCorrelationId()).isEqualTo("req-1");
        assertThat(failure.stage()).isEqualTo(PlanningStage.ROUTE);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.RUNTIME_UNAVAILABLE);
        assertThat(failure.operationAudits()).containsExactly(exception.audit());
    }

    @Test
    void mapsPlanDeadlineFailureToDeadlineExceeded() {
        RuntimeOperationException exception = exception(
                RuntimeOperationType.PLAN,
                RuntimeOperationFailure.DEADLINE,
                PlanningOperationTermination.DEADLINE_EXCEEDED);

        var failure = mapper.map(exception, handle());

        assertThat(failure.stage()).isEqualTo(PlanningStage.PLAN);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);
        assertThat(failure.diagnosticId()).isEqualTo("diag-runtime");
    }

    @Test
    void mapsProtocolAndAuthFailuresToTypedKernelCodes() {
        assertThat(map(RuntimeOperationFailure.PROTOCOL).errorCode())
                .isEqualTo(KernelErrorCode.RUNTIME_CONTRACT_INVALID);
        assertThat(map(RuntimeOperationFailure.AUTHENTICATION).errorCode())
                .isEqualTo(KernelErrorCode.RUNTIME_AUTHENTICATION_FAILED);
        assertThat(map(RuntimeOperationFailure.REPAIR_EXHAUSTED).errorCode())
                .isEqualTo(KernelErrorCode.RUNTIME_OUTPUT_INVALID);
    }

    private com.dylan.agent.planning.model.PlanningFailure map(RuntimeOperationFailure failure) {
        return mapper.map(exception(
                RuntimeOperationType.ROUTE,
                failure,
                PlanningOperationTermination.PROTOCOL_REJECTED), handle());
    }

    private static RuntimeOperationException exception(
            RuntimeOperationType operation,
            RuntimeOperationFailure failure,
            PlanningOperationTermination termination) {
        PlanningOperationAudit audit = PlanningOperationAudit.notReported(operation, 1L, termination);
        return new RuntimeOperationException(operation, failure, audit, "diag-runtime", null);
    }

    private static InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("user", "dylan"),
                new com.dylan.agent.invocation.model.ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                DEADLINE);
    }
}
