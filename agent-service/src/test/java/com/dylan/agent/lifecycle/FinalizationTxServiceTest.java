package com.dylan.agent.lifecycle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.lifecycle.model.InvocationResponseType;
import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentInvocationResultMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;

class FinalizationTxServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-07-02T00:00:00Z"), ZoneOffset.UTC);

    @Test
    void planningCancellationFinalizesInvocationAndTurn() {
        AgentInvocationRecordMapper invocationMapper = mock(AgentInvocationRecordMapper.class);
        AgentTurnMapper turnMapper = mock(AgentTurnMapper.class);
        FinalizationTxService service = new FinalizationTxService(
                invocationMapper,
                mock(AgentInvocationResultMapper.class),
                turnMapper,
                mock(ContextFinalizationParticipant.class),
                new PayloadJsonCodec(new ObjectMapper()),
                mock(ContractRegistry.class),
                CLOCK);
        when(invocationMapper.finalizeTerminal(
                eq("inv-1"),
                eq("CANCELLED"),
                eq("CANCELLED"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已取消或超时。"),
                eq(null),
                any())).thenReturn(1);
        when(turnMapper.finalizeFailure(
                eq("turn-1"),
                eq("inv-1"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已取消或超时。"),
                any())).thenReturn(1);

        var result = service.commitPlanningCancellation(
                handle(),
                PlanningCancellation.beforePlanning("req-1", KernelErrorCode.DEADLINE_EXCEEDED));

        assertThat(result.state()).isEqualTo(InvocationState.CANCELLED);
        assertThat(result.responseType()).isEqualTo(InvocationResponseType.CANCELLED);
        verify(invocationMapper).finalizeTerminal(
                eq("inv-1"),
                eq("CANCELLED"),
                eq("CANCELLED"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已取消或超时。"),
                eq(null),
                any());
        verify(turnMapper).finalizeFailure(
                eq("turn-1"),
                eq("inv-1"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已取消或超时。"),
                any());
    }

    private static InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("USER", "user-1"),
                new ContextOwnerRef("USER", "user-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                CLOCK.instant().plusSeconds(60));
    }
}
