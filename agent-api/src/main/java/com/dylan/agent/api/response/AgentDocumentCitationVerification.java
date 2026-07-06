package com.dylan.agent.api.response;

import java.util.List;

/** 文档生成引用校验摘要。 */
public class AgentDocumentCitationVerification {
    private GroundingStatus status;
    private int removedClaimCount;
    private List<String> invalidCitationIds;
    private String fallbackReason;

    public GroundingStatus getStatus() { return status; }
    public void setStatus(GroundingStatus status) { this.status = status; }
    public int getRemovedClaimCount() { return removedClaimCount; }
    public void setRemovedClaimCount(int removedClaimCount) { this.removedClaimCount = removedClaimCount; }
    public List<String> getInvalidCitationIds() { return invalidCitationIds; }
    public void setInvalidCitationIds(List<String> invalidCitationIds) { this.invalidCitationIds = invalidCitationIds; }
    public String getFallbackReason() { return fallbackReason; }
    public void setFallbackReason(String fallbackReason) { this.fallbackReason = fallbackReason; }
}
