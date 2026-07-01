package com.dylan.agent.conversation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.argThat;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.exception.AgentConversationNotFoundException;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.model.ConversationStatus;
import com.dylan.agent.persistence.entity.AgentConversationEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;

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
        ObjectMapper objectMapper = new ObjectMapper();
        service = new ConversationService(conversationMapper, turnMapper, clock, objectMapper);
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
    @DisplayName("最近 Turn 数量限制透传给 Mapper")
    void shouldLimitRecentTurns() {
        AgentTurnEntity turn = new AgentTurnEntity();
        turn.setUserMessage("问题");
        turn.setAssistantMessage("回答");
        when(turnMapper.selectRecentSucceeded("conv-1", "user-1", 3)).thenReturn(List.of(turn));

        assertThat(service.loadRecentTurns("conv-1", "user-1", 3)).hasSize(2);
        verify(turnMapper).selectRecentSucceeded("conv-1", "user-1", 3);
    }

    @Test
    @DisplayName("CAS 更新为零时失败")
    void shouldFailWhenCompletionCasMisses() {
        when(turnMapper.completeSuccess(anyString(), anyString(), anyString(), anyString(), any(), any()))
                .thenReturn(0);
        assertThatThrownBy(() -> service.completeSuccess(
                "turn-1", AgentIntent.QUERY, AgentResponseType.RESULT, "done", null))
                .isInstanceOf(AgentInternalException.class);
    }

    @Test
    @DisplayName("completeSuccess 含非 null 上下文时序列化写入 contextJson")
    void shouldSerializeNonNullContextToJson() {
        var ctx = new RuntimeQueryContext();
        ctx.setSourceTurnId("turn-1");
        when(turnMapper.completeSuccess(anyString(), anyString(), anyString(), anyString(), any(), any()))
                .thenReturn(1);

        service.completeSuccess("turn-1", AgentIntent.QUERY, AgentResponseType.RESULT, "ok", ctx);

        verify(turnMapper).completeSuccess(eq("turn-1"), eq("QUERY"), eq("RESULT"),
                eq("ok"), argThat(json -> json != null && json.contains("turn-1")), any());
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
}
