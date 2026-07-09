package com.dylan.agent.adapter.api.document;

import java.util.Map;

/** Adapter 层文档检索诊断摘要。 */
public class AdapterDocumentRetrievalDiagnostics {
    private String retrievalMode;
    private Integer keywordHitCount;
    private Integer vectorHitCount;
    private Integer returnedHitCount;
    private Integer fusedCandidateCount;
    private Integer dedupedCandidateCount;
    private Integer rrfK;
    private Integer maxChunksPerDocument;
    private Map<String, Integer> channelHitCounts;
    private Map<String, Double> channelWeights;
    private String permissionEvidenceId;
    private String permissionVersion;
    private String filterDigest;
    private String fusionStrategy;
    private String rerankStatus;
    private String rerankSkippedReason;
    private boolean degraded;
    private String degradationReason;

    public String getRetrievalMode() { return retrievalMode; }
    public void setRetrievalMode(String retrievalMode) { this.retrievalMode = retrievalMode; }
    public Integer getKeywordHitCount() { return keywordHitCount; }
    public void setKeywordHitCount(Integer keywordHitCount) { this.keywordHitCount = keywordHitCount; }
    public Integer getVectorHitCount() { return vectorHitCount; }
    public void setVectorHitCount(Integer vectorHitCount) { this.vectorHitCount = vectorHitCount; }
    public Integer getReturnedHitCount() { return returnedHitCount; }
    public void setReturnedHitCount(Integer returnedHitCount) { this.returnedHitCount = returnedHitCount; }
    public Integer getFusedCandidateCount() { return fusedCandidateCount; }
    public void setFusedCandidateCount(Integer fusedCandidateCount) { this.fusedCandidateCount = fusedCandidateCount; }
    public Integer getDedupedCandidateCount() { return dedupedCandidateCount; }
    public void setDedupedCandidateCount(Integer dedupedCandidateCount) { this.dedupedCandidateCount = dedupedCandidateCount; }
    public Integer getRrfK() { return rrfK; }
    public void setRrfK(Integer rrfK) { this.rrfK = rrfK; }
    public Integer getMaxChunksPerDocument() { return maxChunksPerDocument; }
    public void setMaxChunksPerDocument(Integer maxChunksPerDocument) { this.maxChunksPerDocument = maxChunksPerDocument; }
    public Map<String, Integer> getChannelHitCounts() { return channelHitCounts; }
    public void setChannelHitCounts(Map<String, Integer> channelHitCounts) { this.channelHitCounts = channelHitCounts; }
    public Map<String, Double> getChannelWeights() { return channelWeights; }
    public void setChannelWeights(Map<String, Double> channelWeights) { this.channelWeights = channelWeights; }
    public String getPermissionEvidenceId() { return permissionEvidenceId; }
    public void setPermissionEvidenceId(String permissionEvidenceId) { this.permissionEvidenceId = permissionEvidenceId; }
    public String getPermissionVersion() { return permissionVersion; }
    public void setPermissionVersion(String permissionVersion) { this.permissionVersion = permissionVersion; }
    public String getFilterDigest() { return filterDigest; }
    public void setFilterDigest(String filterDigest) { this.filterDigest = filterDigest; }
    public String getFusionStrategy() { return fusionStrategy; }
    public void setFusionStrategy(String fusionStrategy) { this.fusionStrategy = fusionStrategy; }
    public String getRerankStatus() { return rerankStatus; }
    public void setRerankStatus(String rerankStatus) { this.rerankStatus = rerankStatus; }
    public String getRerankSkippedReason() { return rerankSkippedReason; }
    public void setRerankSkippedReason(String rerankSkippedReason) { this.rerankSkippedReason = rerankSkippedReason; }
    public boolean isDegraded() { return degraded; }
    public void setDegraded(boolean degraded) { this.degraded = degraded; }
    public String getDegradationReason() { return degradationReason; }
    public void setDegradationReason(String degradationReason) { this.degradationReason = degradationReason; }
}
