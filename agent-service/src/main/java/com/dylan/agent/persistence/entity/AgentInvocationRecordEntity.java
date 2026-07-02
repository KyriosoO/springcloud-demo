package com.dylan.agent.persistence.entity;

import java.time.LocalDateTime;

/**
 * 单次 Agent 调用生命周期的权威记录行。
 */
public class AgentInvocationRecordEntity {

    private String id;
    private String invocationType;
    private String originType;
    private String conversationId;
    private String turnId;
    private String subjectType;
    private String subjectId;
    private String ownerType;
    private String ownerId;
    private String scopeType;
    private String scopeId;
    private String agentId;
    private String profileVersion;
    private String requestCorrelationId;
    private String state;
    private String responseType;
    private String checkpointJson;
    private String checkpointHash;
    private String errorCode;
    private String safeMessage;
    private String diagnosticId;
    private LocalDateTime deadlineAt;
    private LocalDateTime createdAt;
    private LocalDateTime checkpointedAt;
    private LocalDateTime completedAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getInvocationType() { return invocationType; }
    public void setInvocationType(String invocationType) { this.invocationType = invocationType; }
    public String getOriginType() { return originType; }
    public void setOriginType(String originType) { this.originType = originType; }
    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }
    public String getTurnId() { return turnId; }
    public void setTurnId(String turnId) { this.turnId = turnId; }
    public String getSubjectType() { return subjectType; }
    public void setSubjectType(String subjectType) { this.subjectType = subjectType; }
    public String getSubjectId() { return subjectId; }
    public void setSubjectId(String subjectId) { this.subjectId = subjectId; }
    public String getOwnerType() { return ownerType; }
    public void setOwnerType(String ownerType) { this.ownerType = ownerType; }
    public String getOwnerId() { return ownerId; }
    public void setOwnerId(String ownerId) { this.ownerId = ownerId; }
    public String getScopeType() { return scopeType; }
    public void setScopeType(String scopeType) { this.scopeType = scopeType; }
    public String getScopeId() { return scopeId; }
    public void setScopeId(String scopeId) { this.scopeId = scopeId; }
    public String getAgentId() { return agentId; }
    public void setAgentId(String agentId) { this.agentId = agentId; }
    public String getProfileVersion() { return profileVersion; }
    public void setProfileVersion(String profileVersion) { this.profileVersion = profileVersion; }
    public String getRequestCorrelationId() { return requestCorrelationId; }
    public void setRequestCorrelationId(String requestCorrelationId) { this.requestCorrelationId = requestCorrelationId; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
    public String getResponseType() { return responseType; }
    public void setResponseType(String responseType) { this.responseType = responseType; }
    public String getCheckpointJson() { return checkpointJson; }
    public void setCheckpointJson(String checkpointJson) { this.checkpointJson = checkpointJson; }
    public String getCheckpointHash() { return checkpointHash; }
    public void setCheckpointHash(String checkpointHash) { this.checkpointHash = checkpointHash; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String errorCode) { this.errorCode = errorCode; }
    public String getSafeMessage() { return safeMessage; }
    public void setSafeMessage(String safeMessage) { this.safeMessage = safeMessage; }
    public String getDiagnosticId() { return diagnosticId; }
    public void setDiagnosticId(String diagnosticId) { this.diagnosticId = diagnosticId; }
    public LocalDateTime getDeadlineAt() { return deadlineAt; }
    public void setDeadlineAt(LocalDateTime deadlineAt) { this.deadlineAt = deadlineAt; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getCheckpointedAt() { return checkpointedAt; }
    public void setCheckpointedAt(LocalDateTime checkpointedAt) { this.checkpointedAt = checkpointedAt; }
    public LocalDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(LocalDateTime completedAt) { this.completedAt = completedAt; }
}
