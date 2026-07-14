package com.dylan.agent.lifecycle;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.core.ExecutionCore;
import com.dylan.agent.kernel.core.ExecutionFailure;
import com.dylan.agent.kernel.core.ExecutionSuccess;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.lifecycle.model.CheckpointResult;
import com.dylan.agent.lifecycle.model.FinalizedInvocationResult;
import com.dylan.agent.lifecycle.model.InvocationResponseType;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.ResolvedClarification;
import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class ExecutionLifecycleServiceTest {

    private static final Instant DEADLINE = Instant.parse("2026-07-02T00:01:00Z");

    private StartTxService startTxService;
    private CheckpointTxService checkpointTxService;
    private FinalizationTxService finalizationTxService;
    private ExecutionCore executionCore;
    private ExecutionLifecycleService service;

    @BeforeEach
    void setUp() {
        startTxService = mock(StartTxService.class);
        checkpointTxService = mock(CheckpointTxService.class);
        finalizationTxService = mock(FinalizationTxService.class);
        executionCore = mock(ExecutionCore.class);
        service = new ExecutionLifecycleService(
                startTxService,
                checkpointTxService,
                finalizationTxService,
                executionCore);
    }

    @Test
    void executeAndFinalizeCheckpointsBeforeCoreAndCommitsSuccess() {
        InvocationHandle handle = handle();
        ExecutablePlanningResult planningResult = planningResult(handle);
        CheckpointResult checkpoint = checkpoint();
        ExecutionSuccess success = new ExecutionSuccess(
                new SecuredResult(
                        AgentExecutionContracts.QUERY_RESULT,
                        "{}".getBytes(StandardCharsets.UTF_8),
                        "done",
                        "summary"),
                List.of(),
                "query.search",
                com.dylan.agent.api.contract.runtime.common.AgentPlanKind.QUERY);
        FinalizedInvocationResult finalized = finalized(handle, InvocationResponseType.SUCCESS);
        when(checkpointTxService.write(handle, planningResult)).thenReturn(checkpoint);
        when(executionCore.execute(any())).thenReturn(success);
        when(finalizationTxService.commitSuccess(handle, checkpoint, success)).thenReturn(finalized);

        FinalizedInvocationResult result = service.executeAndFinalize(
                handle,
                planningResult,
                new CancellationSource().token());

        assertThat(result).isSameAs(finalized);
        InOrder order = inOrder(checkpointTxService, executionCore, finalizationTxService);
        order.verify(checkpointTxService).write(handle, planningResult);
        order.verify(executionCore).execute(any());
        order.verify(finalizationTxService).commitSuccess(handle, checkpoint, success);
    }

    @Test
    void executeAndFinalizeCommitsCancelledExecutionFailureOnCancelledOutcome() {
        InvocationHandle handle = handle();
        ExecutablePlanningResult planningResult = planningResult(handle);
        CheckpointResult checkpoint = checkpoint();
        ExecutionFailure failure = new ExecutionFailure(
                com.dylan.agent.invocation.model.ExecutionStage.CANCELLATION_DEADLINE,
                com.dylan.agent.invocation.model.KernelErrorCode.DEADLINE_EXCEEDED,
                "diag-1",
                true);
        FinalizedInvocationResult finalized = finalized(handle, InvocationResponseType.CANCELLED);
        when(checkpointTxService.write(handle, planningResult)).thenReturn(checkpoint);
        when(executionCore.execute(any())).thenReturn(failure);
        when(finalizationTxService.commitExecutionCancelled(handle, checkpoint, failure)).thenReturn(finalized);

        FinalizedInvocationResult result = service.executeAndFinalize(
                handle,
                planningResult,
                new CancellationSource().token());

        assertThat(result.responseType()).isEqualTo(InvocationResponseType.CANCELLED);
        assertThat(result).isSameAs(finalized);
    }

    @Test
    void finalizeClarificationDoesNotCheckpointOrInvokeCore() {
        InvocationHandle handle = handle();
        ResolvedClarification clarification = mock(ResolvedClarification.class);
        FinalizedInvocationResult finalized = finalized(handle, InvocationResponseType.CLARIFY);
        when(finalizationTxService.commitClarification(handle, clarification)).thenReturn(finalized);

        FinalizedInvocationResult result = service.finalizeClarification(handle, clarification);

        assertThat(result.responseType()).isEqualTo(InvocationResponseType.CLARIFY);
        verifyNoInteractions(checkpointTxService, executionCore);
    }

    @Test
    void commitUnknownReturnsAuthoritativeTerminalAfterReconciliation() {
        InvocationHandle handle = handle();
        ResolvedClarification clarification = mock(ResolvedClarification.class);
        FinalizedInvocationResult authoritative = finalized(handle, InvocationResponseType.CLARIFY);
        when(finalizationTxService.commitClarification(handle, clarification))
                .thenThrow(new IllegalStateException("commit result unknown"));
        when(finalizationTxService.readAuthoritativeTerminal(handle))
                .thenReturn(Optional.of(authoritative));

        FinalizedInvocationResult result = service.finalizeClarification(handle, clarification);

        assertThat(result).isSameAs(authoritative);
        verifyNoInteractions(checkpointTxService, executionCore);
    }

    @Test
    void invalidArtifactIsRejectedBeforeCheckpoint() {
        InvocationHandle handle = handle();
        ExecutablePlanningResult planningResult = planningResult(handle);
        when(planningResult.hasValidArtifactIdentity()).thenReturn(false);

        assertThatThrownBy(() -> service.executeAndFinalize(
                handle,
                planningResult,
                new CancellationSource().token()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("artifact");

        verifyNoInteractions(checkpointTxService, executionCore, finalizationTxService);
    }

    private static CheckpointResult checkpoint() {
        return CheckpointResult.committed(
                CheckpointResult.Status.COMMITTED,
                new CheckpointResult.CommittedCheckpoint("inv-1", "inv-1", "hash"));
    }

    private static ExecutablePlanningResult planningResult(InvocationHandle handle) {
        ExecutablePlanningResult result = mock(ExecutablePlanningResult.class);
        when(result.requestCorrelationId()).thenReturn(handle.requestCorrelationId());
        when(result.invocationId()).thenReturn(handle.invocationId());
        when(result.absoluteDeadline()).thenReturn(handle.absoluteDeadline());
        when(result.hasValidArtifactIdentity()).thenReturn(true);
        return result;
    }

    private static InvocationHandle handle() {
        return InvocationHandle.forChat(
                "inv-1",
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "inv-1",
                new ExecutionSubjectRef("USER", "user-1"),
                new ContextOwnerRef("USER", "user-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent", "profile-v1"),
                DEADLINE);
    }

    private static FinalizedInvocationResult finalized(
            InvocationHandle handle,
            InvocationResponseType responseType) {
        return FinalizedInvocationResult.builder()
                .invocationId(handle.invocationId())
                .origin(handle.origin())
                .state(responseType == InvocationResponseType.CANCELLED
                        ? InvocationState.CANCELLED
                        : InvocationState.COMPLETED)
                .responseType(responseType)
                .safeMessage("ok")
                .build();
    }
}
