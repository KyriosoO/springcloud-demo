package com.dylan.agent.lifecycle;

import com.dylan.agent.application.StartChatCommand;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.model.TurnStatus;
import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import com.dylan.agent.persistence.entity.AgentTurnEntity;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Objects;
import java.util.UUID;

/**
 * 启动事务：创建或校验会话，然后原子创建轮次和调用。
 */
@Service
public class StartTxService {

    private final ConversationService conversationService;
    private final AgentConversationMapper conversationMapper;
    private final AgentTurnMapper turnMapper;
    private final AgentInvocationRecordMapper invocationMapper;
    private final Clock clock;

    public StartTxService(ConversationService conversationService,
                          AgentConversationMapper conversationMapper,
                          AgentTurnMapper turnMapper,
                          AgentInvocationRecordMapper invocationMapper,
                          Clock clock) {
        this.conversationService = Objects.requireNonNull(conversationService);
        this.conversationMapper = Objects.requireNonNull(conversationMapper);
        this.turnMapper = Objects.requireNonNull(turnMapper);
        this.invocationMapper = Objects.requireNonNull(invocationMapper);
        this.clock = Objects.requireNonNull(clock);
    }

    @Transactional
    public StartWriteResult createOrVerify(StartChatCommand command) {
        Objects.requireNonNull(command, "command must not be null");
        ConversationHandle conversation = conversationService.openConversation(
                command.conversationId(), command.userContext().getUserId());
        LocalDateTime now = LocalDateTime.now(clock);
        String invocationId = UUID.randomUUID().toString();
        String turnId = UUID.randomUUID().toString();

        AgentTurnEntity turn = new AgentTurnEntity();
        turn.setId(turnId);
        turn.setConversationId(conversation.conversationId());
        turn.setInvocationId(invocationId);
        turn.setUserId(command.userContext().getUserId());
        turn.setUserMessage(command.message());
        turn.setStatus(TurnStatus.PROCESSING);
        turn.setCreatedAt(now);
        if (turnMapper.insert(turn) != 1) {
            throw new IllegalStateException("create turn failed");
        }
        if (conversationMapper.touchOwned(conversation.conversationId(), command.userContext().getUserId(), now) != 1) {
            throw new IllegalStateException("touch conversation failed");
        }

        InvocationHandle handle = handle(
                invocationId,
                conversation.conversationId(),
                turnId,
                command);
        AgentInvocationRecordEntity entity = record(handle, now);
        if (invocationMapper.insert(entity) != 1) {
            throw new IllegalStateException("create invocation failed");
        }
        return new StartWriteResult(handle);
    }

    private InvocationHandle handle(String invocationId,
                                    String conversationId,
                                    String turnId,
                                    StartChatCommand command) {
        return InvocationHandle.create(
                invocationId,
                InvocationType.CHAT,
                new ChatInvocationOrigin(conversationId, turnId),
                invocationId,
                new ExecutionSubjectRef("USER", command.userContext().getUserId()),
                new ContextOwnerRef("USER", command.userContext().getUserId()),
                new ConversationScope(conversationId),
                command.agentProfileRef(),
                command.absoluteDeadline());
    }

    private AgentInvocationRecordEntity record(InvocationHandle handle, LocalDateTime now) {
        ChatInvocationOrigin origin = (ChatInvocationOrigin) handle.origin();
        AgentInvocationRecordEntity entity = new AgentInvocationRecordEntity();
        entity.setId(handle.invocationId());
        entity.setInvocationType(handle.invocationType().name());
        entity.setOriginType("CHAT");
        entity.setConversationId(origin.conversationId());
        entity.setTurnId(origin.turnId());
        entity.setSubjectType(handle.subject().type());
        entity.setSubjectId(handle.subject().id());
        entity.setOwnerType(handle.owner().type());
        entity.setOwnerId(handle.owner().id());
        entity.setScopeType("CONVERSATION");
        entity.setScopeId(handle.scope().scopeId());
        entity.setAgentId(handle.agentProfileRef().agentId());
        entity.setProfileVersion(handle.agentProfileRef().expectedVersion().orElseThrow());
        entity.setRequestCorrelationId(handle.requestCorrelationId());
        entity.setState(InvocationState.PROCESSING.name());
        entity.setDeadlineAt(LocalDateTime.ofInstant(handle.absoluteDeadline(), clock.getZone()));
        entity.setCreatedAt(now);
        return entity;
    }
}
