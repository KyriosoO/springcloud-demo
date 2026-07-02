package com.dylan.agent.lifecycle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;

import org.junit.jupiter.api.Test;

class InvocationRecoveryServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-07-02T00:00:00Z"), ZoneOffset.UTC);

    @Test
    void recoversExpiredProcessingInvocationAndTurnInOneBoundary() {
        AgentInvocationRecordMapper invocationMapper = mock(AgentInvocationRecordMapper.class);
        AgentTurnMapper turnMapper = mock(AgentTurnMapper.class);
        InvocationRecoveryService service = new InvocationRecoveryService(invocationMapper, turnMapper, CLOCK);
        AgentInvocationRecordEntity expired = new AgentInvocationRecordEntity();
        expired.setId("inv-1");
        expired.setTurnId("turn-1");
        when(invocationMapper.selectExpiredProcessing(LocalDateTime.parse("2026-07-02T00:00:00"), 10))
                .thenReturn(List.of(expired));
        when(invocationMapper.finalizeTerminal(
                eq("inv-1"),
                eq("CANCELLED"),
                eq("CANCELLED"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已超时。"),
                eq("recovery-deadline"),
                any())).thenReturn(1);
        when(turnMapper.finalizeFailure(
                eq("turn-1"),
                eq("inv-1"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已超时。"),
                any())).thenReturn(1);

        int recovered = service.recoverExpiredProcessing(CLOCK.instant(), 10);

        assertThat(recovered).isEqualTo(1);
        verify(invocationMapper).finalizeTerminal(
                eq("inv-1"),
                eq("CANCELLED"),
                eq("CANCELLED"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已超时。"),
                eq("recovery-deadline"),
                any());
        verify(turnMapper).finalizeFailure(
                eq("turn-1"),
                eq("inv-1"),
                eq("DEADLINE_EXCEEDED"),
                eq("请求已超时。"),
                any());
    }
}
