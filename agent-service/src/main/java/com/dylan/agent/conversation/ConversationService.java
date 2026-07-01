package com.dylan.agent.conversation;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.enums.RuntimeRole;
import com.dylan.agent.api.runtime.RuntimeTurn;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.exception.AgentConversationNotFoundException;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.model.ConversationStatus;
import com.dylan.agent.model.TurnStatus;
import com.dylan.agent.persistence.entity.AgentConversationEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Conversation 与 Turn 持久化服务。
 * 每个公开方法使用独立短事务。
 */
@Service
public class ConversationService {

    private static final Logger log = LoggerFactory.getLogger(ConversationService.class);

    private final AgentConversationMapper conversationMapper;
    private final AgentTurnMapper turnMapper;
    private final Clock clock;
    private final ObjectMapper objectMapper;

    public ConversationService(AgentConversationMapper conversationMapper,
                               AgentTurnMapper turnMapper, Clock clock,
                               ObjectMapper objectMapper) {
        this.conversationMapper = conversationMapper;
        this.turnMapper = turnMapper;
        this.clock = clock;
        this.objectMapper = objectMapper;
    }

    /** 打开已有会话或创建新会话。如果 requestedConversationId 非空，加载已有会话并校验所属用户；否则创建新会话。 */
    @Transactional
    public ConversationHandle openConversation(String requestedConversationId, String userId) {
        LocalDateTime now = LocalDateTime.now(clock);
        if (requestedConversationId != null && !requestedConversationId.isBlank()) {
            String trimmed = requestedConversationId.trim();
            // 加载已有会话
            AgentConversationEntity existing = conversationMapper.selectOwned(trimmed, userId);
            if (existing == null) {
                throw new AgentConversationNotFoundException("会话不存在或不属于当前用户。");
            }
            int touched = conversationMapper.touchOwned(trimmed, userId, now);
            if (touched != 1) {
                throw new AgentInternalException("更新 Conversation updated_at 失败。", null);
            }
            return new ConversationHandle(trimmed);
        }
        // 创建新 Conversation
        AgentConversationEntity entity = new AgentConversationEntity();
        entity.setId(UUID.randomUUID().toString());
        entity.setUserId(userId);
        entity.setStatus(ConversationStatus.ACTIVE);
        entity.setCreatedAt(now);
        entity.setUpdatedAt(now);
        int inserted = conversationMapper.insert(entity);
        if (inserted != 1) {
            throw new AgentInternalException("创建 Conversation 失败。", null);
        }
        return new ConversationHandle(entity.getId());
    }

    /** 创建新对话轮次，状态为 PROCESSING。 */
    @Transactional
    public TurnHandle startTurn(String conversationId, String userId, String normalizedMessage) {
        LocalDateTime now = LocalDateTime.now(clock);
        // 再次确认 Conversation 归属
        int touched = conversationMapper.touchOwned(conversationId, userId, now);
        if (touched != 1) {
            throw new AgentConversationNotFoundException("会话不可用或已过期。");
        }
        AgentTurnEntity turn = new AgentTurnEntity();
        turn.setId(UUID.randomUUID().toString());
        turn.setConversationId(conversationId);
        turn.setUserId(userId);
        turn.setUserMessage(normalizedMessage);
        turn.setStatus(TurnStatus.PROCESSING);
        turn.setCreatedAt(now);
        int inserted = turnMapper.insert(turn);
        if (inserted != 1) {
            throw new AgentInternalException("创建 Turn 失败。", null);
        }
        return new TurnHandle(turn.getId());
    }

    /** 加载最近 N 轮对话，按 turn_seq 排序，提取 role + content。 */
    @Transactional(readOnly = true)
    public List<RuntimeTurn> loadRecentTurns(String conversationId, String userId, int limit) {
        List<AgentTurnEntity> turns = turnMapper.selectRecentSucceeded(conversationId, userId, limit);
        // 反转列表为正序
        List<RuntimeTurn> result = new ArrayList<>();
        for (int i = turns.size() - 1; i >= 0; i--) {
            AgentTurnEntity t = turns.get(i);
            RuntimeTurn rt = new RuntimeTurn();
            rt.setRole(RuntimeRole.USER);
            rt.setContent(t.getUserMessage());
            result.add(rt);

            if (t.getAssistantMessage() != null) {
                RuntimeTurn at = new RuntimeTurn();
                at.setRole(RuntimeRole.ASSISTANT);
                at.setContent(t.getAssistantMessage());
                result.add(at);
            }
        }
        if (result.size() <= limit) {
            return result;
        }
        return new ArrayList<>(result.subList(result.size() - limit, result.size()));
    }

    /** 加载最近一次成功 QUERY 的 query_context_json，用于下一轮 MERGE 判断。仅反序列化 RuntimeQueryContext，该前提由 selectLatestSucceededQuery 的 SQL 条件 {@code AND intent = 'QUERY'} 保证。 */
    @Transactional(readOnly = true)
    public RuntimeQueryContext loadLatestQueryContext(String conversationId, String userId) {
        AgentTurnEntity turn = turnMapper.selectLatestSucceededQuery(conversationId, userId);
        if (turn == null || turn.getQueryContextJson() == null || turn.getQueryContextJson().isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(turn.getQueryContextJson(), RuntimeQueryContext.class);
        } catch (JsonProcessingException e) {
            throw new AgentInternalException("解析历史查询上下文失败。", e);
        }
    }

    /** CAS 将 turn 状态从 PROCESSING 更新为 SUCCEEDED，记录 intent/responseType/assistantMessage。contextToPersist 非 null 时序列化写入 query_context_json。 */
    @Transactional
    public void completeSuccess(String turnId, AgentIntent intent, AgentResponseType responseType,
                                String assistantMessage, Object contextToPersist) {
        LocalDateTime now = LocalDateTime.now(clock);
        String contextJson = null;
        if (contextToPersist != null) {
            try {
                contextJson = objectMapper.writeValueAsString(contextToPersist);
            } catch (JsonProcessingException e) {
                throw new AgentInternalException("序列化上下文失败。", e);
            }
        }
        int updated = turnMapper.completeSuccess(turnId,
                intent != null ? intent.name() : null,
                responseType != null ? responseType.name() : null,
                assistantMessage, contextJson, now);
        if (updated != 1) {
            throw new AgentInternalException("Turn completeSuccess CAS 失败: turnId=" + turnId, null);
        }
    }

    /** CAS 将 turn 状态从 PROCESSING 更新为 FAILED，记录错误码和错误消息。 */
    @Transactional
    public void completeFailure(String turnId, AgentErrorCode errorCode, String assistantMessage) {
        LocalDateTime now = LocalDateTime.now(clock);
        int updated = turnMapper.completeFailure(turnId,
                errorCode != null ? errorCode.name() : null,
                assistantMessage, now);
        if (updated != 1) {
            log.error("Turn completeFailure CAS 失败: turnId={}", turnId);
            throw new AgentInternalException("Turn completeFailure 持久化失败。", null);
        }
    }

    /** 定时清理超过保留期的过期会话及其关联 turns。 */
    @Transactional
    public int cleanupExpired(LocalDateTime cutoff) {
        int turnDeleted = turnMapper.deleteBefore(cutoff);
        int convDeleted = conversationMapper.deleteExpiredWithoutTurns(cutoff);
        log.info("Cleanup: deleted {} turns, {} empty conversations before {}", turnDeleted, convDeleted, cutoff);
        return turnDeleted + convDeleted;
    }
}
