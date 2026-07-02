package com.dylan.agent.conversation;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.agent.api.contract.runtime.common.RuntimeTurnProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeTurnRole;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.exception.AgentConversationNotFoundException;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.model.ConversationStatus;
import com.dylan.agent.model.TurnStatus;
import com.dylan.agent.persistence.entity.AgentConversationEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;

/**
 * 会话与轮次持久化服务。
 * 每个公开方法使用独立短事务。
 */
@Service
public class ConversationService {

    private static final Logger log = LoggerFactory.getLogger(ConversationService.class);

    private final AgentConversationMapper conversationMapper;
    private final AgentTurnMapper turnMapper;
    private final Clock clock;

    public ConversationService(AgentConversationMapper conversationMapper,
                               AgentTurnMapper turnMapper, Clock clock) {
        this.conversationMapper = conversationMapper;
        this.turnMapper = turnMapper;
        this.clock = clock;
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
// 创建新会话。
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

    /**
     * D03 历史投影：只向 Runtime 暴露当前调用之前已成功完成的文本轮次。
     */
    @Transactional(readOnly = true)
    public List<RuntimeTurnProjection> loadRecentTurns(InvocationHandle handle, int limit) {
        if (!(handle.origin() instanceof ChatInvocationOrigin origin)) {
            throw new IllegalArgumentException("CHAT history requires ChatInvocationOrigin");
        }
        List<AgentTurnEntity> turns = turnMapper.selectRecentSucceededBeforeInvocation(
                origin.conversationId(),
                handle.subject().id(),
                handle.invocationId(),
                limit);
        List<RuntimeTurnProjection> result = new ArrayList<>();
        for (int i = turns.size() - 1; i >= 0; i--) {
            AgentTurnEntity turn = turns.get(i);
            result.add(turnProjection(RuntimeTurnRole.USER, turn.getUserMessage()));
            if (turn.getAssistantMessage() != null && !turn.getAssistantMessage().isBlank()) {
                result.add(turnProjection(RuntimeTurnRole.ASSISTANT, turn.getAssistantMessage()));
            }
        }
        if (result.size() <= limit) {
            return result;
        }
        return new ArrayList<>(result.subList(result.size() - limit, result.size()));
    }

    private RuntimeTurnProjection turnProjection(RuntimeTurnRole role, String content) {
        RuntimeTurnProjection projection = new RuntimeTurnProjection();
        projection.setRole(role);
        projection.setContent(content);
        return projection;
    }

    /** 定时清理超过保留期的过期会话及其关联轮次。 */
    @Transactional
    public int cleanupExpired(LocalDateTime cutoff) {
        int turnDeleted = turnMapper.deleteBefore(cutoff);
        int convDeleted = conversationMapper.deleteExpiredWithoutTurns(cutoff);
        log.info("Cleanup: deleted {} turns, {} empty conversations before {}", turnDeleted, convDeleted, cutoff);
        return turnDeleted + convDeleted;
    }
}
