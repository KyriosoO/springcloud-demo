package com.dylan.agent.persistence.entity;

import java.time.LocalDateTime;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.model.TurnStatus;

/**
 * 轮次持久化实体。
 */
public class AgentTurnEntity {

    private String id;
    private String conversationId;
    private String invocationId;
    private String userId;
    private String userMessage;
    private AgentResponseType responseType;
    private String assistantMessage;
    private TurnStatus status;
    private AgentErrorCode errorCode;
    private LocalDateTime createdAt;
    private LocalDateTime completedAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }
    public String getInvocationId() { return invocationId; }
    public void setInvocationId(String invocationId) { this.invocationId = invocationId; }
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    public String getUserMessage() { return userMessage; }
    public void setUserMessage(String userMessage) { this.userMessage = userMessage; }
    public AgentResponseType getResponseType() { return responseType; }
    public void setResponseType(AgentResponseType responseType) { this.responseType = responseType; }
    public String getAssistantMessage() { return assistantMessage; }
    public void setAssistantMessage(String assistantMessage) { this.assistantMessage = assistantMessage; }
    public TurnStatus getStatus() { return status; }
    public void setStatus(TurnStatus status) { this.status = status; }
    public AgentErrorCode getErrorCode() { return errorCode; }
    public void setErrorCode(AgentErrorCode errorCode) { this.errorCode = errorCode; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(LocalDateTime completedAt) { this.completedAt = completedAt; }
}
