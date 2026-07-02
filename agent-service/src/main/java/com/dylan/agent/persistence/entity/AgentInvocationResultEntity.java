package com.dylan.agent.persistence.entity;

import java.time.LocalDateTime;

/**
 * 已终结调用的过滤后结果行。
 */
public class AgentInvocationResultEntity {

    private String id;
    private String invocationId;
    private String outputContractSchema;
    private String outputContractVersion;
    private String payloadJson;
    private String safeMessage;
    private String safeSummary;
    private LocalDateTime createdAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getInvocationId() { return invocationId; }
    public void setInvocationId(String invocationId) { this.invocationId = invocationId; }
    public String getOutputContractSchema() { return outputContractSchema; }
    public void setOutputContractSchema(String outputContractSchema) { this.outputContractSchema = outputContractSchema; }
    public String getOutputContractVersion() { return outputContractVersion; }
    public void setOutputContractVersion(String outputContractVersion) { this.outputContractVersion = outputContractVersion; }
    public String getPayloadJson() { return payloadJson; }
    public void setPayloadJson(String payloadJson) { this.payloadJson = payloadJson; }
    public String getSafeMessage() { return safeMessage; }
    public void setSafeMessage(String safeMessage) { this.safeMessage = safeMessage; }
    public String getSafeSummary() { return safeSummary; }
    public void setSafeSummary(String safeSummary) { this.safeSummary = safeSummary; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
