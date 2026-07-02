package com.dylan.agent.conversation;

import com.dylan.agent.api.contract.runtime.common.RuntimeTurnRole;
import com.dylan.agent.exception.AgentConversationNotFoundException;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.model.ConversationStatus;
import com.dylan.agent.persistence.entity.AgentConversationEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("ConversationService")
class ConversationServiceTest {

    private AgentConversationMapper conversationMapper;
    private AgentTurnMapper turnMapper;
    private ConversationService service;

    @BeforeEach
    void setUp() {
        conversationMapper = mock(AgentConversationMapper.class);
        turnMapper = mock(AgentTurnMapper.class);
        Clock clock = Clock.fixed(Instant.parse("2026-06-18T10:00:00Z"), ZoneOffset.UTC);
        service = new ConversationService(conversationMapper, turnMapper, clock);
    }

    @Test
    @DisplayName("新建会话")
    void shouldCreateConversation() {
        when(conversationMapper.insert(any())).thenReturn(1);

        ConversationHandle handle = service.openConversation(null, "user-1");

        assertThat(handle.conversationId()).isNotBlank();
        verify(conversationMapper).insert(any(AgentConversationEntity.class));
    }

    @Test
    @DisplayName("同用户加载并 touch")
    void shouldLoadOwnedConversation() {
        AgentConversationEntity entity = new AgentConversationEntity();
        entity.setId("conv-1");
        entity.setUserId("user-1");
        entity.setStatus(ConversationStatus.ACTIVE);
        when(conversationMapper.selectOwned("conv-1", "user-1")).thenReturn(entity);
        when(conversationMapper.touchOwned(eq("conv-1"), eq("user-1"), any())).thenReturn(1);

        assertThat(service.openConversation(" conv-1 ", "user-1").conversationId()).isEqualTo("conv-1");
    }

    @Test
    @DisplayName("跨用户或不存在会话统一拒绝")
    void shouldRejectUnownedConversation() {
        when(conversationMapper.selectOwned("conv-1", "other")).thenReturn(null);

        assertThatThrownBy(() -> service.openConversation("conv-1", "other"))
                .isInstanceOf(AgentConversationNotFoundException.class);
    }

    @Test
    @DisplayName("D03 history 只通过 invocation 绑定查询")
    void shouldLoadRecentTurnsByInvocationHandle() {
        AgentTurnEntity turn = new AgentTurnEntity();
        turn.setUserMessage("问题");
        turn.setAssistantMessage("回答");
        when(turnMapper.selectRecentSucceededBeforeInvocation("conv-1", "user-1", "inv-1", 4))
                .thenReturn(List.of(turn));

        var history = service.loadRecentTurns(handle(), 4);

        assertThat(history).hasSize(2);
        assertThat(history.get(0).getRole()).isEqualTo(RuntimeTurnRole.USER);
        assertThat(history.get(1).getRole()).isEqualTo(RuntimeTurnRole.ASSISTANT);
        verify(turnMapper).selectRecentSucceededBeforeInvocation("conv-1", "user-1", "inv-1", 4);
    }

    @Test
    @DisplayName("清理只使用传入 cutoff")
    void shouldCleanupByCutoff() {
        LocalDateTime cutoff = LocalDateTime.of(2026, 6, 10, 0, 0);
        when(turnMapper.deleteBefore(cutoff)).thenReturn(2);
        when(conversationMapper.deleteExpiredWithoutTurns(cutoff)).thenReturn(1);

        assertThat(service.cleanupExpired(cutoff)).isEqualTo(3);
    }

    @Test
    @DisplayName("编排入口不持有事务")
    void orchestratorDoesNotDeclareTransaction() throws Exception {
        var method = com.dylan.agent.application.AgentOrchestrator.class.getMethod(
                "chat",
                com.dylan.agent.model.AgentUserContext.class,
                com.dylan.agent.api.request.AgentChatRequest.class);
        assertThat(method.getAnnotation(Transactional.class)).isNull();
        assertThat(com.dylan.agent.application.AgentOrchestrator.class.getAnnotation(Transactional.class)).isNull();
    }

    private static InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "corr-1",
                new ExecutionSubjectRef("USER", "user-1"),
                new ContextOwnerRef("USER", "user-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                Instant.parse("2026-06-18T10:01:00Z"));
    }
}
