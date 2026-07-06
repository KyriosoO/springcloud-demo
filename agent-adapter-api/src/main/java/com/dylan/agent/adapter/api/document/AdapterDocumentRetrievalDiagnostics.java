package com.dylan.agent.adapter.api.document;

/** Adapter 层文档检索诊断摘要。 */
public class AdapterDocumentRetrievalDiagnostics {
    private String retrievalMode;
    private Integer keywordHitCount;
    private Integer vectorHitCount;
    private String fusionStrategy;
    private boolean degraded;
    private String degradationReason;

    public String getRetrievalMode() { return retrievalMode; }
    public void setRetrievalMode(String retrievalMode) { this.retrievalMode = retrievalMode; }
    public Integer getKeywordHitCount() { return keywordHitCount; }
    public void setKeywordHitCount(Integer keywordHitCount) { this.keywordHitCount = keywordHitCount; }
    public Integer getVectorHitCount() { return vectorHitCount; }
    public void setVectorHitCount(Integer vectorHitCount) { this.vectorHitCount = vectorHitCount; }
    public String getFusionStrategy() { return fusionStrategy; }
    public void setFusionStrategy(String fusionStrategy) { this.fusionStrategy = fusionStrategy; }
    public boolean isDegraded() { return degraded; }
    public void setDegraded(boolean degraded) { this.degraded = degraded; }
    public String getDegradationReason() { return degradationReason; }
    public void setDegradationReason(String degradationReason) { this.degradationReason = degradationReason; }
}
