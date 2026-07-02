package com.dylan.agent.lifecycle;

import com.dylan.agent.application.StartChatCommand;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class StartTxServiceTest {

    private static final Clock CLOCK = Clock.fixed(
            Instant.parse("2026-07-02T00:00:00Z"),
            ZoneOffset.UTC);
    private static final Instant DEADLINE = Instant.parse("2026-07-02T00:01:00Z");

    private ConversationService conversationService;
    private AgentConversationMapper conversationMapper;
    private AgentTurnMapper turnMapper;
    private AgentInvocationRecordMapper invocationMapper;
    private StartTxService service;

    @BeforeEach
    void setUp() {
        conversationService = mock(ConversationService.class);
        conversationMapper = mock(AgentConversationMapper.class);
        turnMapper = mock(AgentTurnMapper.class);
        invocationMapper = mock(AgentInvocationRecordMapper.class);
        service = new StartTxService(
                conversationService,
                conversationMapper,
                turnMapper,
                invocationMapper,
                CLOCK);
    }

    @Test
    void createsTurnAndInvocationWithSameInvocationId() {
        when(conversationService.openConversation(null, "user-1"))
                .thenReturn(new ConversationHandle("conv-1"));
        when(conversationMapper.touchOwned(eq("conv-1"), eq("user-1"), any())).thenReturn(1);
        when(turnMapper.insert(any())).thenReturn(1);
        when(invocationMapper.insert(any())).thenReturn(1);
        ArgumentCaptor<AgentTurnEntity> turnCaptor = ArgumentCaptor.forClass(AgentTurnEntity.class);
        ArgumentCaptor<AgentInvocationRecordEntity> invocationCaptor =
                ArgumentCaptor.forClass(AgentInvocationRecordEntity.class);

        StartWriteResult result = service.createOrVerify(command());

        org.mockito.Mockito.verify(turnMapper).insert(turnCaptor.capture());
        org.mockito.Mockito.verify(invocationMapper).insert(invocationCaptor.capture());
        AgentTurnEntity turn = turnCaptor.getValue();
        AgentInvocationRecordEntity invocation = invocationCaptor.getValue();
        assertThat(turn.getInvocationId()).isEqualTo(result.handle().invocationId());
        assertThat(invocation.getId()).isEqualTo(result.handle().invocationId());
        assertThat(invocation.getTurnId()).isEqualTo(turn.getId());
        assertThat(invocation.getState()).isEqualTo("PROCESSING");
        assertThat(result.handle().requestCorrelationId()).isEqualTo(result.handle().invocationId());
    }

    private static StartChatCommand command() {
        return new StartChatCommand(
                new AgentUserContext("user-1", Set.of("ROLE_AGENT_USER")),
                null,
                "查询员工",
                AgentProfileRef.of("agent", "profile-v1"),
                DEADLINE);
    }
}
