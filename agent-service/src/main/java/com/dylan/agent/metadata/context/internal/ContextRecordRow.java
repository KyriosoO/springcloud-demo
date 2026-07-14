package com.dylan.agent.metadata.context.internal;

import java.time.LocalDateTime;

/**
 * agent_context_record 的 MyBatis 行结构。
 */
public class ContextRecordRow {

    private String contextId;
    private String ownerType;
    private String ownerId;
    private String scopeType;
    private String scopeId;
    private String contextType;
    private String contractNamespace;
    private String contractName;
    private String contractVersion;
    private long recordVersion;
    private String protectedPayloadJson;
    private String sourceCapabilityId;
    private String sourceInvocationId;
    private String sourceDomain;
    private boolean readable;
    private LocalDateTime expiresAt;
    private LocalDateTime updatedAt;

    public String getContextId() { return contextId; }
    public void setContextId(String contextId) { this.contextId = contextId; }
    public String getOwnerType() { return ownerType; }
    public void setOwnerType(String ownerType) { this.ownerType = ownerType; }
    public String getOwnerId() { return ownerId; }
    public void setOwnerId(String ownerId) { this.ownerId = ownerId; }
    public String getScopeType() { return scopeType; }
    public void setScopeType(String scopeType) { this.scopeType = scopeType; }
    public String getScopeId() { return scopeId; }
    public void setScopeId(String scopeId) { this.scopeId = scopeId; }
    public String getContextType() { return contextType; }
    public void setContextType(String contextType) { this.contextType = contextType; }
    public String getContractNamespace() { return contractNamespace; }
    public void setContractNamespace(String contractNamespace) { this.contractNamespace = contractNamespace; }
    public String getContractName() { return contractName; }
    public void setContractName(String contractName) { this.contractName = contractName; }
    public String getContractVersion() { return contractVersion; }
    public long getRecordVersion() { return recordVersion; }
    public void setRecordVersion(long recordVersion) { this.recordVersion = recordVersion; }
    public void setContractVersion(String contractVersion) { this.contractVersion = contractVersion; }
    public String getProtectedPayloadJson() { return protectedPayloadJson; }
    public void setProtectedPayloadJson(String protectedPayloadJson) { this.protectedPayloadJson = protectedPayloadJson; }
    public String getSourceCapabilityId() { return sourceCapabilityId; }
    public void setSourceCapabilityId(String sourceCapabilityId) { this.sourceCapabilityId = sourceCapabilityId; }
    public String getSourceInvocationId() { return sourceInvocationId; }
    public void setSourceInvocationId(String sourceInvocationId) { this.sourceInvocationId = sourceInvocationId; }
    public String getSourceDomain() { return sourceDomain; }
    public void setSourceDomain(String sourceDomain) { this.sourceDomain = sourceDomain; }
    public boolean isReadable() { return readable; }
    public void setReadable(boolean readable) { this.readable = readable; }
    public LocalDateTime getExpiresAt() { return expiresAt; }
    public void setExpiresAt(LocalDateTime expiresAt) { this.expiresAt = expiresAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
