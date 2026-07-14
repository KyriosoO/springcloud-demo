package com.dylan.agent.api.response;

/** 文档证据覆盖情况。 */
public class AgentDocumentCoverage {

    private int requestedDocumentCount;
    private boolean requestedCountKnown;
    private int coveredDocumentCount;
    private int evidenceCount;
    private boolean truncated;

    public int getRequestedDocumentCount() { return requestedDocumentCount; }
    public void setRequestedDocumentCount(int requestedDocumentCount) { this.requestedDocumentCount = requestedDocumentCount; }
    public boolean isRequestedCountKnown() { return requestedCountKnown; }
    public void setRequestedCountKnown(boolean requestedCountKnown) { this.requestedCountKnown = requestedCountKnown; }
    public int getCoveredDocumentCount() { return coveredDocumentCount; }
    public void setCoveredDocumentCount(int coveredDocumentCount) { this.coveredDocumentCount = coveredDocumentCount; }
    public int getEvidenceCount() { return evidenceCount; }
    public void setEvidenceCount(int evidenceCount) { this.evidenceCount = evidenceCount; }
    public boolean isTruncated() { return truncated; }
    public void setTruncated(boolean truncated) { this.truncated = truncated; }
}
