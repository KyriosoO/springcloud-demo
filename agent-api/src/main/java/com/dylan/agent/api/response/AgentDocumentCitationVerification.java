package com.dylan.agent.api.response;

import java.util.List;

/** 文档生成引用校验摘要。 */
public class AgentDocumentCitationVerification {
    private GroundingStatus status;
    private int boundUnitCount;
    private int visibleCitationCount;

    public GroundingStatus getStatus() { return status; }
    public void setStatus(GroundingStatus status) { this.status = status; }
    public int getBoundUnitCount() { return boundUnitCount; }
    public void setBoundUnitCount(int boundUnitCount) { this.boundUnitCount = boundUnitCount; }
    public int getVisibleCitationCount() { return visibleCitationCount; }
    public void setVisibleCitationCount(int visibleCitationCount) { this.visibleCitationCount = visibleCitationCount; }
}
